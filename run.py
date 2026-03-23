#!/usr/bin/env python3
"""Low VRAM Institute — autonomous Parameter Golf runner."""
from __future__ import annotations

import argparse
import base64
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import parameter_golf

#Paths & constants

ROOT = Path(__file__).resolve().parent
STATE_DIR = ROOT / "state"
LOGS_DIR = ROOT / "logs"
CONFIG_DIR = ROOT / "config"
RUNS_DIR = ROOT / "output" / "runs"
REPORTS_DIR = ROOT / "output" / "reports"

HEARTBEAT_S = 2
BASE_BACKOFF = 10
MAX_BACKOFF = 300
MIN_FREE_DISK = 2_000_000_000
STALE_LOCK_S = 3600


def _emit(msg: str) -> None:
    print(f"[lab] {msg}", flush=True)


def _load_runtime() -> dict[str, Any]:
    p = CONFIG_DIR / "runtime.json"
    return json.loads(p.read_text()) if p.exists() else {}


#Ledger (state/ledger.jsonl)

def ledger_rows() -> list[dict[str, Any]]:
    p = STATE_DIR / "ledger.jsonl"
    if not p.exists():
        return []
    return [json.loads(ln) for ln in p.read_text().splitlines() if ln.strip()]


def _append_ledger(row: dict[str, Any]) -> None:
    with (STATE_DIR / "ledger.jsonl").open("a") as f:
        f.write(json.dumps(row, sort_keys=True) + "\n")


def _row_val_bpb(row: dict[str, Any]) -> float | None:
    value = row.get("final_val_bpb", row.get("score"))
    return float(value) if value is not None else None


def _is_valid_main_track(row: dict[str, Any]) -> bool:
    if "valid_main_track" in row:
        return bool(row.get("valid_main_track"))
    return bool(row.get("under_16mb"))


def _best_valid_row(rows: list[dict[str, Any]]) -> dict[str, Any] | None:
    valid = [r for r in rows if _is_valid_main_track(r) and _row_val_bpb(r) is not None]
    return min(valid, key=lambda r: _row_val_bpb(r) or float("inf")) if valid else None


def _valid_improvement_run_ids(rows: list[dict[str, Any]]) -> set[str]:
    best_so_far: float | None = None
    winners: set[str] = set()
    for row in rows:
        if not _is_valid_main_track(row):
            continue
        val_bpb = _row_val_bpb(row)
        if val_bpb is None:
            continue
        if best_so_far is None or val_bpb < best_so_far:
            winners.add(str(row.get("run_id", "")))
            best_so_far = val_bpb
    return winners


def best_score() -> float | None:
    rows = ledger_rows()
    scores = [score for score in (_row_val_bpb(r) for r in rows) if score is not None]
    return min(scores) if scores else None


def _best_run_id() -> str | None:
    row = _best_valid_row(ledger_rows())
    return str(row.get("run_id")) if row else None


def _best_script_path() -> Path:
    return STATE_DIR / "best_script.py"


def _best_published_script_path() -> Path | None:
    run_id = _best_run_id()
    if not run_id:
        return None
    path = RUNS_DIR / run_id / "train_gpt_mlx.py"
    return path if path.exists() else None


def best_script() -> str | None:
    published = _best_published_script_path()
    if published:
        script = published.read_text()
        path = _best_script_path()
        text = script.rstrip() + "\n"
        if not path.exists() or path.read_text() != text:
            path.write_text(text)
        return script

    path = _best_script_path()
    if path.exists():
        return path.read_text()
    return None



def _save_best(script: str) -> None:
    _best_script_path().write_text(script.rstrip() + "\n")


def _next_plan_path() -> Path:
    return STATE_DIR / "next_plan.md"


def _pending_plan_path() -> Path:
    return STATE_DIR / "pending_plan.md"


def _planner_lock_path() -> Path:
    return STATE_DIR / "planner.lock"


def _read_plan_file(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    text = path.read_text()
    marker = "\n## Rationale\n"
    if marker not in text:
        path.unlink()
        return None

    head, body = text.split(marker, 1)
    meta: dict[str, str] = {}
    for line in head.splitlines()[1:]:
        line = line.strip()
        if not line:
            continue
        key, sep, value = line.partition(":")
        if not sep:
            continue
        meta[key.strip()] = value.strip()

    rationale = body.rstrip()
    modified_script: str | None = None
    script_marker = "\n## Script\n```python\n"
    if script_marker in body:
        rationale, script_block = body.split(script_marker, 1)
        modified_script, _, _ = script_block.partition("\n```")
        modified_script = modified_script.rstrip()

    title = meta.get("title", "")
    track = meta.get("track", "")
    if not title or not isinstance(track, str):
        path.unlink()
        return None

    return {
        "run_id": meta.get("run_id") or None,
        "base_best_run_id": meta.get("base_best_run_id") or None,
        "plan": {
            "title": title,
            "rationale": rationale.strip(),
            "modified_script": modified_script,
            "track": track,
        },
    }


def _write_plan_file(
    path: Path,
    plan_dict: dict[str, Any],
    *,
    run_id: str | None = None,
    base_best_run_id: str | None = None,
) -> None:
    lines = ["# Plan", ""]
    if run_id:
        lines.append(f"run_id: {run_id}")
    if base_best_run_id:
        lines.append(f"base_best_run_id: {base_best_run_id}")
    lines.append(f"title: {plan_dict.get('title', '')}")
    lines.append(f"track: {plan_dict.get('track', '')}")
    lines.extend([
        "",
        "## Rationale",
        str(plan_dict.get("rationale", "")).strip() or "(none)",
    ])
    script = plan_dict.get("modified_script")
    if script is not None:
        lines.extend(["", "## Script", "```python", script.rstrip(), "```"])
    path.write_text("\n".join(lines).rstrip() + "\n")


def _load_pending_plan() -> dict[str, Any] | None:
    path = _pending_plan_path()
    data = _read_plan_file(path)
    if not data:
        return None
    run_id = data.get("run_id")
    if not isinstance(run_id, str) or not run_id or (RUNS_DIR / run_id).exists():
        path.unlink(missing_ok=True)
        return None
    return {"run_id": run_id, "plan": data["plan"]}


def _save_pending_plan(run_id: str, plan_dict: dict[str, Any]) -> None:
    _write_plan_file(_pending_plan_path(), plan_dict, run_id=run_id)


def _clear_pending_plan(run_id: str | None = None) -> None:
    path = _pending_plan_path()
    if not path.exists():
        return
    if run_id is None:
        path.unlink()
        return
    data = _read_plan_file(path)
    if not data or data.get("run_id") == run_id:
        path.unlink()


def _load_next_plan(expected_best_run_id: str | None, *, consume: bool = False) -> dict[str, Any] | None:
    path = _next_plan_path()
    data = _read_plan_file(path)
    if not data:
        return None
    if data.get("base_best_run_id") != (expected_best_run_id or ""):
        path.unlink(missing_ok=True)
        return None
    if consume:
        path.unlink(missing_ok=True)
    return data["plan"]


def _save_next_plan(plan_dict: dict[str, Any], base_best_run_id: str) -> None:
    _write_plan_file(_next_plan_path(), plan_dict, base_best_run_id=base_best_run_id)


def _clear_next_plan() -> None:
    _next_plan_path().unlink(missing_ok=True)


#Render context for prompt (the memory system)

def render_context() -> str:
    """Render a bounded summary for the planner."""
    rows = ledger_rows()
    if not rows:
        return "No runs yet."

    best_row = _best_valid_row(rows) or min(rows, key=lambda r: _row_val_bpb(r) or float("inf"))
    best_val = _row_val_bpb(best_row)
    assert best_val is not None
    improvement_ids = _valid_improvement_run_ids(rows)
    improvements = [r for r in rows if str(r.get("run_id", "")) in improvement_ids]
    last_imp_idx = max(
        (i for i, r in enumerate(rows) if str(r.get("run_id", "")) in improvement_ids),
        default=0,
    )
    plateau = len(rows) - last_imp_idx - 1

    lines: list[str] = []
    lines.append(
        f"Best valid final_int8_zlib_roundtrip_exact val_bpb: {best_val:.4f} "
        f"({best_row['run_id']}) | {best_row.get('title', '')}"
    )
    lines.append(f"Runs: {len(rows)} | Improvements: {len(improvements)} | Plateau streak: {plateau}")
    lines.append("")

    lines.append("Recent runs:")
    for row in rows[-8:]:
        val_bpb = _row_val_bpb(row)
        if val_bpb is None:
            continue
        delta = val_bpb - best_val
        run_id = str(row.get("run_id", ""))
        tag = "WIN" if run_id in improvement_ids else f"{delta:+.4f}"
        parts = []
        parts.append("mod" if row.get("has_modified_script") else "base")
        parts.append("valid" if _is_valid_main_track(row) else "invalid")
        lines.append(
            f"- {row['run_id']} | final_int8_zlib_roundtrip_exact val_bpb {val_bpb:.4f} "
            f"{tag} | {', '.join(parts)} | {row.get('title', '')}"
        )
    lines.append("")

    if improvements:
        lines.append("Best path:")
        for row in improvements[-6:]:
            val_bpb = _row_val_bpb(row)
            if val_bpb is None:
                continue
            mod = "base" if not row.get("has_modified_script") else "mod"
            lines.append(f"- {row['run_id']} | {val_bpb:.4f} | {mod} | {row.get('title', '')}")
        lines.append("")

    misses = [
        r for r in rows
        if r.get("has_modified_script")
        and (str(r.get("run_id", "")) not in improvement_ids or not _is_valid_main_track(r))
    ]
    if misses:
        lines.append("Closest misses:")
        seen: set[str] = set()
        for row in sorted(misses, key=lambda r: _row_val_bpb(r) or float("inf")):
            val_bpb = _row_val_bpb(row)
            if val_bpb is None:
                continue
            title = row.get("title", "")
            if title in seen:
                continue
            seen.add(title)
            status = "invalid" if not _is_valid_main_track(row) else "valid"
            lines.append(f"- {title} | {val_bpb - best_val:+.4f} | {status}")
            if len(seen) == 5:
                break
        lines.append("")

    return "\n".join(lines)


#Update state after run

def _update_after_run(run_id: str, plan_dict: dict, raw: dict) -> None:
    rows = ledger_rows()
    prior_scores = [_row_val_bpb(r) for r in rows if _is_valid_main_track(r)]
    prior_best = min((score for score in prior_scores if score is not None), default=None)
    score = raw["score"]
    diag = raw.get("diagnostics", {})
    valid_run = bool(raw["passed"]) and bool(diag.get("under_16mb")) and bool(diag.get("within_train_wallclock", True))
    improved = valid_run and (prior_best is None or score < prior_best)

    if improved and plan_dict.get("modified_script"):
        _save_best(plan_dict["modified_script"])

    _append_ledger({
        "run_id": run_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "title": plan_dict.get("title", ""),
        "final_val_bpb": score,
        "train_time_ms": diag.get("train_time_ms"),
        "passed": raw["passed"],
        "has_modified_script": bool(plan_dict.get("modified_script")),
        "quantized_bytes": diag.get("quantized_bytes"),
        "code_bytes": diag.get("code_bytes"),
        "artifact_bytes": diag.get("artifact_bytes"),
        "under_16mb": diag.get("under_16mb"),
        "within_train_wallclock": diag.get("within_train_wallclock"),
        "valid_main_track": valid_run,
        "track": plan_dict.get("track", ""),
    })


#Codex (planning)

class CodexError(RuntimeError):
    def __init__(self, msg: str, retryable: bool = True) -> None:
        super().__init__(msg)
        self.retryable = retryable


def _is_retryable_codex_failure(detail: str) -> bool:
    lowered = detail.lower()
    if any(marker in lowered for marker in [
        "invalid model",
        "unknown model",
        "login required",
        "expired",
        "authentication",
        "unauthorized",
    ]):
        return False
    if re.search(r"\b(429|5\d\d)\b", lowered):
        return True
    return any(marker in lowered for marker in [
        "rate limit",
        "timeout",
        "unavailable",
        "overloaded",
        "stream disconnected",
        "sending request",
        "connection",
        "dns",
        "resolve host",
    ])


def _call_codex(
    prompt: str,
    model: str | None = None,
    reasoning_effort: str | None = None,
    service_tier: str | None = None,
) -> dict:
    binary = shutil.which("codex")
    if not binary:
        raise CodexError("Codex CLI not found in PATH.", retryable=False)

    schema = {
        "type": "object",
        "required": ["title", "rationale", "modified_script"],
        "properties": {
            "title": {"type": "string"},
            "rationale": {"type": "string"},
            "modified_script": {"type": ["string", "null"]},
        },
        "additionalProperties": False,
    }

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        schema_path = tmp / "schema.json"
        output_path = tmp / "output.json"
        schema_path.write_text(json.dumps(schema))

        cmd = [binary, "exec", "--skip-git-repo-check", "--cd", str(ROOT),
               "--output-schema", str(schema_path), "--output-last-message", str(output_path),
               "--color", "never"]
        if model:
            cmd.extend(["--model", model])
        if reasoning_effort:
            cmd.extend(["-c", f'model_reasoning_effort=\"{reasoning_effort}\"'])
        if service_tier:
            cmd.extend(["-c", f'service_tier=\"{service_tier}\"'])

        r = subprocess.run(cmd, input=prompt, capture_output=True, text=True, check=False)  # noqa: S603
        if r.returncode != 0:
            detail = "\n".join(filter(None, [r.stdout.strip(), r.stderr.strip()]))
            retryable = _is_retryable_codex_failure(detail)
            raise CodexError(f"Codex failed: {detail[:200]}", retryable=retryable)
        if not output_path.exists():
            raise CodexError("Codex produced no output.", retryable=False)
        try:
            return json.loads(output_path.read_text())
        except json.JSONDecodeError as exc:
            raise CodexError(f"Invalid JSON: {exc}", retryable=False) from exc

#Plan (prompt from config/prompt.md template)

def _build_prompt(run_errors: list[str] | None = None) -> str:
    # Template
    template_path = CONFIG_DIR / "prompt.md"
    template = template_path.read_text() if template_path.exists() else "Return a plan as JSON.\n{rules}\n{history}\n"

    # Rules
    rules_path = CONFIG_DIR / "parameter_golf_rules.md"
    rules = rules_path.read_text().strip() if rules_path.exists() else ""

    best = best_script()
    if best:
        best_script_section = (
            "## Current Best Script\n"
            "Read `state/best_script.py` from the workspace and return the full modified script.\n"
        )
    else:
        best_script_section = (
            "## Current Script\n"
            "Read `third_party/parameter-golf/train_gpt_mlx.py` from the workspace and return the full modified script.\n"
        )

    # Errors
    errors_section = ""
    if run_errors:
        errors_section = "## Previous Run Errors\n\nFix the issue or try a different approach.\n\n"
        for i, err in enumerate(run_errors):
            errors_section += f"- Attempt {i + 1}: {err}\n"

    return template.format(
        rules=rules,
        history=render_context(),
        best_script_section=best_script_section,
        errors_section=errors_section,
    )


def plan(run_errors: list[str] | None = None) -> dict:
    runtime = _load_runtime()
    codex_cfg = runtime.get("codex", {})
    track = runtime.get("parameter_golf", {}).get("local_track", "mac_mini_official_like")
    has_runs = best_score() is not None

    if not has_runs:
        return {
            "title": "Establish baseline",
            "rationale": "Guaranteed stock baseline on the Mac mini before autonomous modifications begin.",
            "modified_script": None,
            "track": track,
        }

    if codex_cfg.get("enabled"):
        prompt = _build_prompt(run_errors)
        payload = _call_codex(
            prompt,
            model=codex_cfg.get("model"),
            reasoning_effort=codex_cfg.get("reasoning_effort"),
            service_tier=codex_cfg.get("service_tier"),
        )
        return {
            "title": payload["title"],
            "rationale": payload["rationale"],
            "modified_script": payload.get("modified_script") or None,
            "track": track,
        }

    # Heuristic fallback (codex disabled)
    return {
        "title": "Refine current best",
        "rationale": "Exploiting current best.",
        "modified_script": best_script(),
        "track": track,
    }


def plan_next() -> None:
    best_run_id = _best_run_id()
    if not best_run_id:
        return
    with _planner_lock():
        if _load_next_plan(best_run_id):
            return
        p = plan()
        _save_next_plan(p, best_run_id)
        _emit(f"next plan ready: {p.get('title', '?')}")


#Publish (per-run artifacts + CSV + SVG + git push)

def _publish(run_id: str, plan_dict: dict, raw: dict) -> None:
    run_dir = RUNS_DIR / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    diag = raw.get("diagnostics", {})
    prov = raw.get("provenance", {})
    valid_main_track = bool(raw["passed"]) and bool(diag.get("under_16mb")) and bool(diag.get("within_train_wallclock", True))

    # Per-run artifacts
    (run_dir / "diff.patch").write_text((raw.get("patch") or "").rstrip() + "\n")
    if raw.get("run_log"):
        (run_dir / "run.log").write_text(raw["run_log"].rstrip() + "\n")
    if raw.get("train_script"):
        (run_dir / "train_gpt_mlx.py").write_text(raw["train_script"].rstrip() + "\n")
    req_path = prov.get("requirements_path")
    if req_path and Path(req_path).exists():
        shutil.copy2(req_path, run_dir / "requirements.txt")
    quant_path = prov.get("quantized_model_path")
    if quant_path and Path(quant_path).exists():
        shutil.copy2(quant_path, run_dir / Path(quant_path).name)
    artifact = {
        "code_bytes": diag.get("code_bytes", 0),
        "model_bytes": diag.get("quantized_bytes", 0),
        "artifact_bytes": diag.get("artifact_bytes", 0),
        "under_16mb": bool(diag.get("under_16mb")),
        "train_time_ms": diag.get("train_time_ms"),
        "within_train_wallclock": bool(diag.get("within_train_wallclock", True)),
        "valid_main_track": valid_main_track,
        "limit_bytes": 16_000_000,
    }
    (run_dir / "artifact_size.json").write_text(json.dumps(artifact, indent=2, sort_keys=True) + "\n")

    # Submission JSON (Parameter Golf format)
    runtime = _load_runtime()
    owner = runtime.get("github", {}).get("owner", "low-vram-institute")
    (run_dir / "submission.json").write_text(json.dumps({
        "submitter": owner, "val_bpb": raw["score"], "run_id": run_id,
        "hardware": "Mac mini M4 16GB", "track": plan_dict.get("track", ""),
        "runtime_seconds": raw["runtime_seconds"],
        "has_modified_script": bool(plan_dict.get("modified_script")),
        "title": plan_dict.get("title", ""),
        "rationale": plan_dict.get("rationale", ""),
        "train_time_ms": diag.get("train_time_ms"),
        "code_bytes": diag.get("code_bytes", 0),
        "model_bytes": diag.get("quantized_bytes", 0),
        "artifact_bytes": diag.get("artifact_bytes", 0),
        "under_16mb": bool(diag.get("under_16mb")),
        "within_train_wallclock": bool(diag.get("within_train_wallclock", True)),
        "valid_main_track": valid_main_track,
    }, indent=2, sort_keys=True) + "\n")
    (run_dir / "README.md").write_text(
        "\n".join([
            f"# {run_id}",
            "",
            f"- final_int8_zlib_roundtrip_exact val_bpb: {raw['score']:.6f}",
            f"- runtime_seconds: {raw['runtime_seconds']:.2f}",
            f"- train_time_ms: {diag.get('train_time_ms')}",
            f"- track: {plan_dict.get('track', '')}",
            f"- title: {plan_dict.get('title', '')}",
            f"- code_bytes: {diag.get('code_bytes', 0)}",
            f"- model_bytes: {diag.get('quantized_bytes', 0)}",
            f"- artifact_bytes: {diag.get('artifact_bytes', 0)}",
            f"- passed: {bool(raw['passed'])}",
            f"- under_16mb: {bool(diag.get('under_16mb'))}",
            f"- within_train_wallclock: {bool(diag.get('within_train_wallclock', True))}",
            f"- valid_main_track: {valid_main_track}",
            "",
            "This is a Mac mini official-like local run package.",
            "The intended mismatch versus official leaderboard submissions is hardware.",
        ]) + "\n"
    )

    # Reports
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    (REPORTS_DIR / "history.csv").write_text(_render_csv())
    (REPORTS_DIR / "history.svg").write_text(_render_svg())

    _git_push(run_id)


def _render_csv() -> str:
    rows = ledger_rows()
    lines = ["run_id,final_val_bpb,modified,improved,title"]
    best_so_far: float | None = None
    for row in rows:
        score = _row_val_bpb(row)
        if score is None:
            continue
        valid = _is_valid_main_track(row)
        improved = valid and (best_so_far is None or score < best_so_far)
        if improved:
            best_so_far = score
        title = str(row.get("title", "")).replace(",", " ")
        lines.append(f"{row.get('run_id', '')},{score:.6f},{row.get('has_modified_script', False)},{improved},{title}")
    return "\n".join(lines) + "\n"


def _render_svg() -> str:
    rows = ledger_rows()
    best_so_far: float | None = None
    pts: list[dict] = []
    for row in rows:
        s = _row_val_bpb(row)
        if s is None or not _is_valid_main_track(row):
            continue
        if best_so_far is None or s < best_so_far:
            best_so_far = s
            pts.append(row)

    w, h = 760, 280
    lm, rm, tm, bm = 70, 20, 36, 56
    if not pts:
        return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}">'
                '<text x="20" y="40" font-family="monospace" font-size="16">No history yet.</text></svg>\n')

    scores = [_row_val_bpb(r) for r in pts]
    scores = [s for s in scores if s is not None]
    mn, mx = min(scores), max(scores)
    if mx == mn:
        mx = mn + 0.01
    pad = max((mx - mn) * 0.15, 0.001)
    mn_a, mx_a = mn - pad, mx + pad

    def xf(i: int) -> float:
        return w / 2 if len(pts) == 1 else lm + i * ((w - lm - rm) / (len(pts) - 1))

    def yf(v: float) -> float:
        return h - bm - ((v - mn_a) / (mx_a - mn_a)) * (h - tm - bm)

    polyline = " ".join(f"{xf(i):.1f},{yf(_row_val_bpb(r) or 0.0):.1f}" for i, r in enumerate(pts))
    dots = "".join(
        f'<circle cx="{xf(i):.1f}" cy="{yf(_row_val_bpb(r) or 0.0):.1f}" r="4" fill="#0f766e"/>'
        f'<text x="{xf(i):.1f}" y="{h-28}" text-anchor="middle" font-family="monospace" font-size="10">'
        f'{r["run_id"].split("_")[-1]}</text>'
        for i, r in enumerate(pts))
    ticks = "".join(
        f'<line x1="{lm}" y1="{tm+j*(h-tm-bm)/4:.1f}" x2="{w-rm}" y2="{tm+j*(h-tm-bm)/4:.1f}" stroke="#e2e8f0"/>'
        f'<text x="{lm-8}" y="{tm+j*(h-tm-bm)/4+4:.1f}" text-anchor="end" font-family="monospace" font-size="10" fill="#475569">'
        f'{mx_a-j*(mx_a-mn_a)/4:.4f}</text>'
        for j in range(5))
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}">'
        '<rect width="100%" height="100%" fill="#f8fafc"/>'
        f'<text x="20" y="24" font-family="monospace" font-size="16">Best Score By Run</text>'
        + ticks
        + f'<polyline fill="none" stroke="#0f766e" stroke-width="3" points="{polyline}"/>'
        + dots + '</svg>\n')


#Git push


def _git_push(run_id: str) -> None:
    _git_commit(run_id)
    _git_remote_push()


def _git_commit(run_id: str) -> None:
    if not (ROOT / ".git").exists():
        return
    for cmd in [
        ["git", "add", "output/reports", "output/runs",
         "state/README.md", "state/ledger.jsonl", "state/best_script.py"],
        ["git", "commit", "-m", f"Publish {run_id}"],
    ]:
        r = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, check=False)  # noqa: S603
        if r.returncode != 0 and not ("commit" in cmd and "nothing to commit" in r.stdout.lower()):
            return


def _git_remote_push() -> None:
    if not (ROOT / ".git").exists():
        return
    runtime = _load_runtime()
    pub = runtime.get("publishing", {})
    allowed = pub.get("allowed_remote_url")
    branch = pub.get("branch", "main")
    if not allowed:
        return
    r = subprocess.run(["git", "remote", "get-url", "origin"], cwd=ROOT, capture_output=True, text=True, check=False)  # noqa: S603
    if r.returncode != 0 or r.stdout.strip() != allowed:
        return

    token = os.environ.get("GITHUB_TOKEN")
    base = ["git"]
    if token:
        basic = base64.b64encode(f"x-access-token:{token}".encode()).decode("ascii")
        base = ["git", "-c", "credential.helper=", "-c", "core.askPass=",
                "-c", f"http.extraHeader=AUTHORIZATION: basic {basic}"]

    r = subprocess.run(base + ["push", "origin", branch], cwd=ROOT, capture_output=True, text=True, check=False)  # noqa: S603
    if r.returncode != 0:
        _emit(f"git push failed: {r.stderr.strip()[:200]}")


#Core loop

@contextmanager
def _run_lock():
    lock = STATE_DIR / "run.lock"
    if lock.exists():
        try:
            data = json.loads(lock.read_text())
            age = (datetime.now(timezone.utc) - datetime.fromisoformat(data["locked_at"])).total_seconds()
            if age <= STALE_LOCK_S:
                raise RuntimeError("Another run appears active.")
        except (json.JSONDecodeError, KeyError):
            pass
        lock.unlink()
    lock.write_text(json.dumps({"locked_at": datetime.now(timezone.utc).isoformat()}) + "\n")
    try:
        yield
    finally:
        if lock.exists():
            lock.unlink()


@contextmanager
def _planner_lock():
    lock = _planner_lock_path()
    if lock.exists():
        try:
            data = json.loads(lock.read_text())
            age = (datetime.now(timezone.utc) - datetime.fromisoformat(data["locked_at"])).total_seconds()
            if age <= STALE_LOCK_S:
                raise RuntimeError("Planner already active.")
        except (json.JSONDecodeError, KeyError):
            pass
        lock.unlink()
    lock.write_text(json.dumps({"locked_at": datetime.now(timezone.utc).isoformat()}) + "\n")
    try:
        yield
    finally:
        if lock.exists():
            lock.unlink()


def _planner_active() -> bool:
    lock = _planner_lock_path()
    if not lock.exists():
        return False
    try:
        data = json.loads(lock.read_text())
        age = (datetime.now(timezone.utc) - datetime.fromisoformat(data["locked_at"])).total_seconds()
    except (json.JSONDecodeError, KeyError):
        lock.unlink()
        return False
    if age <= STALE_LOCK_S:
        return True
    lock.unlink()
    return False


def _start_next_planner() -> None:
    best_run_id = _best_run_id()
    if not best_run_id or _load_next_plan(best_run_id) or _planner_active():
        return
    subprocess.Popen(  # noqa: S603
        [sys.executable, str(ROOT / "run.py"), "plan-next"],
        cwd=ROOT,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )


def _next_run_id() -> str:
    prefix = datetime.now(timezone.utc).strftime("%Y_%m_%d_run_")
    existing = [p.name for p in RUNS_DIR.iterdir() if p.is_dir() and p.name.startswith(prefix)] if RUNS_DIR.exists() else []
    return prefix + f"{len(existing) + 1:04d}"


def run_once(start_async_planner: bool = False) -> str:
    if shutil.disk_usage(ROOT).free < MIN_FREE_DISK:
        raise RuntimeError("Low disk space.")

    runtime = _load_runtime()
    pg_config = runtime.get("parameter_golf", {})

    with _run_lock():
        prior_best_run_id = _best_run_id()
        pending = _load_pending_plan()
        queued = None if pending else _load_next_plan(prior_best_run_id, consume=True)
        run_id = pending["run_id"] if pending else _next_run_id()
        _emit(f"starting {run_id}")

        run_errors: list[str] = []
        p: dict[str, Any] | None = pending["plan"] if pending else queued
        for attempt in range(3):
            if attempt > 0 or p is None:
                p = plan(run_errors=run_errors or None)
            _save_pending_plan(run_id, p)
            suffix = ""
            if attempt == 0 and pending:
                suffix = " [pending]"
            elif attempt == 0 and queued:
                suffix = " [next]"
            _emit(f"plan: {p.get('title', '?')}{suffix}")
            if start_async_planner and attempt == 0:
                _start_next_planner()

            try:
                raw = parameter_golf.run(run_id, p, pg_config, LOGS_DIR)
                break
            except Exception as exc:
                _clear_pending_plan(run_id)
                run_errors.append(str(exc))
                _emit(f"attempt {attempt + 1}/3 failed: {exc}")
                if attempt == 2:
                    raise RuntimeError("Failed after 3 attempts") from exc

        _emit(f"score={raw['score']:.4f} passed={raw['passed']}")
        _update_after_run(run_id, p, raw)
        if _best_run_id() != prior_best_run_id:
            _clear_next_plan()
        _publish(run_id, p, raw)
        _clear_pending_plan(run_id)
        _emit(f"published {run_id}")
        return run_id


def daemon(max_cycles: int | None = None) -> None:
    for d in [STATE_DIR, LOGS_DIR, RUNS_DIR, REPORTS_DIR]:
        d.mkdir(parents=True, exist_ok=True)

    failures = 0
    cycles = 0
    _emit("daemon started")
    while max_cycles is None or cycles < max_cycles:
        try:
            run_once(start_async_planner=True)
            failures = 0
            cycles += 1
            _emit(f"cycle done; sleeping {HEARTBEAT_S}s")
            time.sleep(HEARTBEAT_S)
        except KeyboardInterrupt:
            _emit("shutdown")
            raise
        except CodexError as exc:
            failures += 1
            delay = min(BASE_BACKOFF * (2 ** (failures - 1)), MAX_BACKOFF)
            _emit(f"codex unavailable; retry in {delay}s")
            if not exc.retryable:
                raise
            time.sleep(delay)
        except Exception as exc:  # noqa: BLE001
            failures += 1
            delay = min(BASE_BACKOFF * (2 ** (failures - 1)), MAX_BACKOFF)
            _emit(f"failed: {exc}; retry in {delay}s")
            time.sleep(delay)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Low VRAM Institute")
    sub = parser.add_subparsers(dest="cmd")
    sub.add_parser("plan-next")
    sub.add_parser("run-once")
    d = sub.add_parser("daemon")
    d.add_argument("--max-cycles", type=int, default=None)
    args = parser.parse_args()

    for d in [STATE_DIR, LOGS_DIR, RUNS_DIR, REPORTS_DIR]:
        d.mkdir(parents=True, exist_ok=True)

    if args.cmd == "plan-next":
        plan_next()
    elif args.cmd == "run-once":
        run_once()
    elif args.cmd == "daemon":
        daemon(max_cycles=args.max_cycles)
    else:
        parser.print_help()
