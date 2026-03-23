#!/usr/bin/env python3
"""Low VRAM Institute — autonomous Parameter Golf runner."""
from __future__ import annotations

import argparse
import base64
import json
import os
import shutil
import subprocess
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


def best_score() -> float | None:
    rows = ledger_rows()
    return min(r["score"] for r in rows) if rows else None


def best_script() -> str | None:
    p = STATE_DIR / "best_script.json"
    if not p.exists():
        return None
    data = json.loads(p.read_text())
    return data.get("modified_script") if isinstance(data, dict) else None



def _save_best(run_id: str, score: float, title: str, script: str, patch: str) -> None:
    (STATE_DIR / "best_script.json").write_text(json.dumps({
        "run_id": run_id, "score": score, "title": title, "modified_script": script,
    }, indent=2, sort_keys=True) + "\n")
    (STATE_DIR / "best_diff.patch").write_text(patch.rstrip() + "\n")


#Curve analysis

def _analyze_curve(metrics_jsonl: str) -> dict[str, Any]:
    """Analyze training curve. Returns shape + trajectory details."""
    if not metrics_jsonl:
        return {"shape": "no_data"}
    scores: list[float] = []
    for line in metrics_jsonl.strip().splitlines():
        try:
            row = json.loads(line.strip())
            scores.append(row.get("val_bpb", row.get("val_loss", 0)))
        except (json.JSONDecodeError, ValueError):
            continue
    if len(scores) < 2:
        return {"shape": "too_short"}
    mid = len(scores) // 2
    early = scores[0] - scores[mid]
    late = scores[mid] - scores[-1]
    if early > 0.001 and late > 0.001:
        shape = "improving"
    elif early > 0.001:
        shape = "plateaued"
    elif late > 0.001:
        shape = "slow_start"
    else:
        shape = "flat"
    return {
        "shape": shape,
        "first_val": round(scores[0], 4),
        "last_val": round(scores[-1], 4),
        "drop": round(scores[0] - scores[-1], 4),
    }


#Render context for prompt (the memory system)

def render_context() -> str:
    """Render ledger into dense prompt context. Scales to 1000+ runs.

    Sections:
    1. Scoreboard — best score, run count, plateau streak
    2. Recent 15 — full diagnostics + score delta from best
    3. Near-misses — within 3% of best, with rationale (worth refining)
    4. Failures — deduplicated, sorted by delta (disasters last)
    5. Improvements — the compound path to current best
    """
    rows = ledger_rows()
    if not rows:
        return "No runs yet."
    best_row = min(rows, key=lambda r: r["score"])
    best_val = best_row["score"]
    improvements = [r for r in rows if r.get("improved_best")]
    last_imp_idx = max((i for i, r in enumerate(rows) if r.get("improved_best")), default=0)
    plateau = len(rows) - last_imp_idx - 1

    lines: list[str] = []

    # 1. Scoreboard
    lines.append(f"Best: {best_val:.4f} ({best_row['run_id']}) | {best_row.get('title', '')}")
    lines.append(f"Runs: {len(rows)} | Improvements: {len(improvements)} | Plateau streak: {plateau}")
    lines.append("")

    # 2. Recent runs with diagnostics + delta + trajectory
    lines.append("Recent runs:")
    for row in rows[-15:]:
        delta = row["score"] - best_val
        tag = "WIN" if row.get("improved_best") else f"+{delta:.4f}"
        mod = "mod" if row.get("has_modified_script") else "base"
        parts = []
        if row.get("total_steps"):
            parts.append(f"{row['total_steps']}steps")
        elif row.get("step_count"):
            parts.append(f"{row['step_count']}steps")
        if row.get("total_tokens"):
            parts.append(f"{row['total_tokens']/1e6:.1f}Mtok")
        if row.get("runtime_seconds"):
            parts.append(f"{row['runtime_seconds']:.0f}s")
        if row.get("avg_tok_s"):
            parts.append(f"{row['avg_tok_s']:.0f}tok/s")
        if row.get("peak_mb"):
            parts.append(f"{row['peak_mb']:.0f}MB")
        if row.get("curve") and row["curve"] != "no_data":
            curve_str = row["curve"]
            if row.get("first_val") and row.get("last_val"):
                curve_str += f" {row['first_val']:.3f}→{row['last_val']:.3f}"
            parts.append(curve_str)
        diag = f" [{', '.join(parts)}]" if parts else ""
        lines.append(f"- {row['run_id']} | {row['score']:.4f} {tag} | {mod}{diag} | {row.get('title', '')}")
    lines.append("")

    # Collect all non-improving modified runs
    failed = [r for r in rows if not r.get("improved_best") and r.get("has_modified_script")]

    # 3. Near-misses (within 3% of best) — promising, worth refining
    near = [r for r in failed if r["score"] < best_val * 1.03]
    if near:
        near.sort(key=lambda r: r["score"])
        lines.append("Near-misses (within 3% of best — promising, try refining):")
        seen: set[str] = set()
        diffs_shown = 0
        for r in near:
            t = r.get("title", "")
            if t in seen:
                continue
            seen.add(t)
            delta = r["score"] - best_val
            rationale = r.get("rationale", "")
            if len(rationale) > 80:
                rationale = rationale[:77] + "..."
            hint = f" — {rationale}" if rationale else ""
            lines.append(f"- {t} (+{delta:.4f}){hint}")
            # Include abbreviated diff for top 3 near-misses
            if diffs_shown < 3:
                diff_path = RUNS_DIR / r["run_id"] / "diff.patch"
                if diff_path.exists():
                    diff_lines = diff_path.read_text().strip().splitlines()
                    # Show only changed lines (max 15 lines)
                    key_lines = [l for l in diff_lines if l.startswith(("+", "-")) and not l.startswith(("+++", "---"))][:15]
                    if key_lines:
                        lines.append("  diff: " + " | ".join(key_lines[:8]))
                        diffs_shown += 1
            if len(seen) >= 10:
                break
        lines.append("")

    # 4. Failures — deduplicated, sorted by how bad (delta ascending)
    if failed:
        by_title: dict[str, dict] = {}
        for r in failed:
            t = r.get("title", "")
            if t not in by_title or r["score"] < by_title[t]["score"]:
                by_title[t] = r
        sorted_fails = sorted(by_title.values(), key=lambda r: r["score"])
        lines.append(f"Failed ideas ({len(by_title)} unique, don't repeat):")
        for r in sorted_fails[:20]:
            delta = r["score"] - best_val
            lines.append(f"- {r.get('title', '')} (+{delta:.4f})")
        if len(by_title) > 20:
            lines.append(f"  ... and {len(by_title) - 20} more")
        lines.append("")

    # 5. Speed-score insight — does more steps = better score?
    runs_with_steps = [r for r in rows if r.get("step_count") and r.get("step_count") > 0]
    if len(runs_with_steps) >= 3:
        by_steps = sorted(runs_with_steps, key=lambda r: r["step_count"], reverse=True)
        fastest = by_steps[0]
        slowest = by_steps[-1]
        if fastest["step_count"] != slowest["step_count"]:
            lines.append("Speed insight:")
            lines.append(f"- Most steps: {fastest['step_count']} → {fastest['score']:.4f} ({fastest.get('title', '')})")
            lines.append(f"- Fewest steps: {slowest['step_count']} → {slowest['score']:.4f} ({slowest.get('title', '')})")
            if fastest["score"] < slowest["score"]:
                lines.append("- Pattern: more steps correlates with better scores")
            lines.append("")

    # 6. Improvement path — how we got to current best (last 30)
    if improvements:
        lines.append("Improvements (path to current best):")
        shown = improvements[-30:]
        if len(improvements) > 30:
            lines.append(f"  ({len(improvements) - 30} earlier improvements omitted)")
        for r in shown:
            mod = "+script" if r.get("has_modified_script") else "baseline"
            lines.append(f"- {r['run_id']} {r['score']:.4f} [{mod}] {r.get('title', '')}")
        lines.append("")

    # 7. Last run's training curve excerpt (last 5 steps) — helps spot cutoff issues
    if rows:
        last = rows[-1]
        metrics_path = RUNS_DIR / last["run_id"] / "metrics.jsonl"
        if metrics_path.exists():
            try:
                mlines = metrics_path.read_text().strip().splitlines()
                tail = mlines[-5:] if len(mlines) >= 5 else mlines
                vals = []
                for ml in tail:
                    try:
                        m = json.loads(ml)
                        step = m.get("step", "?")
                        vbpb = m.get("val_bpb", m.get("val_loss", "?"))
                        vals.append(f"step {step}: {vbpb}")
                    except (json.JSONDecodeError, ValueError):
                        continue
                if vals:
                    lines.append(f"Last run curve tail ({last['run_id']}):")
                    lines.append("  " + " → ".join(vals))
                    lines.append("")
            except OSError:
                pass

    return "\n".join(lines)


#Update state after run

def _update_after_run(run_id: str, plan_dict: dict, raw: dict) -> None:
    rows = ledger_rows()
    prior_best = min((r["score"] for r in rows), default=None)
    score = raw["score"]
    improved = prior_best is None or score < prior_best

    if improved and plan_dict.get("modified_script"):
        _save_best(run_id, score, plan_dict.get("title", ""), plan_dict["modified_script"], raw["patch"])

    diag = raw.get("diagnostics", {})
    curve = _analyze_curve(raw.get("metrics_jsonl", ""))

    _append_ledger({
        "run_id": run_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "title": plan_dict.get("title", ""),
        "rationale": plan_dict.get("rationale", ""),
        "score": score,
        "val_loss": diag.get("val_loss"),
        "passed": raw["passed"],
        "has_modified_script": bool(plan_dict.get("modified_script")),
        "improved_best": improved,
        "runtime_seconds": raw["runtime_seconds"],
        "step_count": diag.get("step_count", 0),
        "total_steps": diag.get("total_steps"),
        "total_tokens": diag.get("total_tokens"),
        "avg_tok_s": diag.get("avg_tok_s"),
        "peak_mb": diag.get("peak_mb"),
        "active_mb": diag.get("active_mb"),
        "quantized_bytes": diag.get("quantized_bytes"),
        "code_bytes": diag.get("code_bytes"),
        "artifact_bytes": diag.get("artifact_bytes"),
        "under_16mb": diag.get("under_16mb"),
        "curve": curve.get("shape", "no_data"),
        "curve_drop": curve.get("drop"),
        "first_val": curve.get("first_val"),
        "last_val": curve.get("last_val"),
        "track": plan_dict.get("track", ""),
    })


#Codex (planning)

class CodexError(RuntimeError):
    def __init__(self, msg: str, retryable: bool = True) -> None:
        super().__init__(msg)
        self.retryable = retryable


def _call_codex(prompt: str, model: str | None = None, reasoning_effort: str | None = None) -> dict:
    binary = shutil.which("codex")
    if not binary:
        raise CodexError("Codex CLI not found in PATH.")

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

        r = subprocess.run(cmd, input=prompt, capture_output=True, text=True, check=False)  # noqa: S603
        if r.returncode != 0:
            detail = "\n".join(filter(None, [r.stdout.strip(), r.stderr.strip()]))
            retryable = any(k in detail.lower() for k in [
                "rate limit", "quota", "timeout", "unavailable", "overloaded",
                "try again", "429", "503", "login required", "expired"])
            raise CodexError(f"Codex failed: {detail[:200]}", retryable=retryable)
        if not output_path.exists():
            raise CodexError("Codex produced no output.")
        try:
            return json.loads(output_path.read_text())
        except json.JSONDecodeError as exc:
            raise CodexError(f"Invalid JSON: {exc}") from exc


def _fetch_ideas(runtime: dict) -> str:
    if not shutil.which("gh"):
        return ""
    repo = runtime.get("github", {})
    slug = f"{repo.get('owner', '')}/{repo.get('repo', '')}"
    if not slug.strip("/"):
        return ""
    r = subprocess.run(["gh", "issue", "list", "-R", slug, "--json", "title,body", "--limit", "10"],
                       capture_output=True, text=True, check=False)
    if r.returncode != 0:
        return ""
    issues = json.loads(r.stdout) if r.stdout.strip() else []
    if not issues:
        return ""
    lines = ["## Community Ideas (GitHub Issues)"]
    for iss in issues:
        body = (iss.get("body") or "").replace("\n", " ").strip()[:120]
        lines.append(f"- {iss['title']}: {body}" if body else f"- {iss['title']}")
    return "\n".join(lines)


#Plan (prompt from config/prompt.md template)

def _build_prompt(run_errors: list[str] | None = None) -> str:
    runtime = _load_runtime()

    # Template
    template_path = CONFIG_DIR / "prompt.md"
    template = template_path.read_text() if template_path.exists() else "Return a plan as JSON.\n{rules}\n{history}\n{script}\n"

    # Rules
    rules_path = CONFIG_DIR / "parameter_golf_rules.md"
    rules = rules_path.read_text().strip() if rules_path.exists() else ""

    # Training script (original baseline)
    ws_path = runtime.get("parameter_golf", {}).get("workspace", "")
    original_script = ""
    if ws_path:
        sp = Path(ws_path) / "train_gpt_mlx.py"
        if sp.exists():
            try:
                original_script = sp.read_text()
            except OSError:
                pass

    # After the first run, Codex only sees the best script — original is irrelevant
    best = best_script()
    if best:
        best_script_section = f"## Current Best Script (start from this)\n\n```python\n{best}\n```"
        script = ""
    else:
        best_script_section = ""
        script = f"```python\n{original_script}\n```" if original_script else "(script not available)"

    # Community ideas from GitHub issues
    ideas = _fetch_ideas(runtime)

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
        script=script,
        ideas=ideas,
        errors_section=errors_section,
    )


def plan(run_errors: list[str] | None = None) -> dict:
    runtime = _load_runtime()
    codex_cfg = runtime.get("codex", {})
    track = runtime.get("parameter_golf", {}).get("local_track", "mac_mini_official_like")

    if codex_cfg.get("enabled"):
        prompt = _build_prompt(run_errors)
        payload = _call_codex(
            prompt,
            model=codex_cfg.get("model"),
            reasoning_effort=codex_cfg.get("reasoning_effort"),
        )
        return {
            "title": payload["title"],
            "rationale": payload["rationale"],
            "modified_script": payload.get("modified_script") or None,
            "track": track,
        }

    # Heuristic fallback (codex disabled)
    has_runs = best_score() is not None
    return {
        "title": "Establish baseline" if not has_runs else "Refine current best",
        "rationale": "Baseline needed." if not has_runs else "Exploiting current best.",
        "modified_script": best_script() if has_runs else None,
        "track": track,
    }


#Publish (per-run artifacts + CSV + SVG + git push)

def _publish(run_id: str, plan_dict: dict, raw: dict) -> None:
    run_dir = RUNS_DIR / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    diag = raw.get("diagnostics", {})
    prov = raw.get("provenance", {})

    # Per-run artifacts
    (run_dir / "diff.patch").write_text((raw.get("patch") or "").rstrip() + "\n")
    if raw.get("run_log"):
        (run_dir / "run.log").write_text(raw["run_log"].rstrip() + "\n")
    if raw.get("metrics_jsonl"):
        (run_dir / "metrics.jsonl").write_text(raw["metrics_jsonl"].rstrip() + "\n")
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
        "code_bytes": diag.get("code_bytes", 0),
        "model_bytes": diag.get("quantized_bytes", 0),
        "artifact_bytes": diag.get("artifact_bytes", 0),
        "under_16mb": bool(diag.get("under_16mb")),
    }, indent=2, sort_keys=True) + "\n")
    (run_dir / "README.md").write_text(
        "\n".join([
            f"# {run_id}",
            "",
            f"- score: {raw['score']:.6f}",
            f"- runtime_seconds: {raw['runtime_seconds']:.2f}",
            f"- track: {plan_dict.get('track', '')}",
            f"- title: {plan_dict.get('title', '')}",
            f"- code_bytes: {diag.get('code_bytes', 0)}",
            f"- model_bytes: {diag.get('quantized_bytes', 0)}",
            f"- artifact_bytes: {diag.get('artifact_bytes', 0)}",
            f"- under_16mb: {bool(diag.get('under_16mb'))}",
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
    lines = ["run_id,score,modified,improved,title"]
    best_so_far: float | None = None
    for row in rows:
        score = row.get("score")
        if score is None:
            continue
        improved = best_so_far is None or score < best_so_far
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
        s = row.get("score")
        if s is None:
            continue
        if best_so_far is None or s < best_so_far:
            best_so_far = s
            pts.append(row)

    w, h = 760, 280
    lm, rm, tm, bm = 70, 20, 36, 56
    if not pts:
        return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}">'
                '<text x="20" y="40" font-family="monospace" font-size="16">No history yet.</text></svg>\n')

    scores = [r["score"] for r in pts]
    mn, mx = min(scores), max(scores)
    if mx == mn:
        mx = mn + 0.01
    pad = max((mx - mn) * 0.15, 0.001)
    mn_a, mx_a = mn - pad, mx + pad

    def xf(i: int) -> float:
        return w / 2 if len(pts) == 1 else lm + i * ((w - lm - rm) / (len(pts) - 1))

    def yf(v: float) -> float:
        return h - bm - ((v - mn_a) / (mx_a - mn_a)) * (h - tm - bm)

    polyline = " ".join(f"{xf(i):.1f},{yf(r['score']):.1f}" for i, r in enumerate(pts))
    dots = "".join(
        f'<circle cx="{xf(i):.1f}" cy="{yf(r["score"]):.1f}" r="4" fill="#0f766e"/>'
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
        ["git", "add", "output/reports", "output/runs"],
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


def _next_run_id() -> str:
    prefix = datetime.now(timezone.utc).strftime("%Y_%m_%d_run_")
    existing = [p.name for p in RUNS_DIR.iterdir() if p.is_dir() and p.name.startswith(prefix)] if RUNS_DIR.exists() else []
    return prefix + f"{len(existing) + 1:04d}"


def run_once() -> str:
    if shutil.disk_usage(ROOT).free < MIN_FREE_DISK:
        raise RuntimeError("Low disk space.")

    runtime = _load_runtime()
    pg_config = runtime.get("parameter_golf", {})

    with _run_lock():
        run_id = _next_run_id()
        _emit(f"starting {run_id}")

        run_errors: list[str] = []
        for attempt in range(3):
            p = plan(run_errors=run_errors or None)
            _emit(f"plan: {p.get('title', '?')}")

            try:
                raw = parameter_golf.run(run_id, p, pg_config, LOGS_DIR)
                break
            except Exception as exc:
                run_errors.append(str(exc))
                _emit(f"attempt {attempt + 1}/3 failed: {exc}")
                if attempt == 2:
                    raise RuntimeError("Failed after 3 attempts") from exc

        _emit(f"score={raw['score']:.4f} passed={raw['passed']}")
        _update_after_run(run_id, p, raw)
        _publish(run_id, p, raw)
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
            run_once()
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
    sub.add_parser("run-once")
    d = sub.add_parser("daemon")
    d.add_argument("--max-cycles", type=int, default=None)
    args = parser.parse_args()

    for d in [STATE_DIR, LOGS_DIR, RUNS_DIR, REPORTS_DIR]:
        d.mkdir(parents=True, exist_ok=True)

    if args.cmd == "run-once":
        run_once()
    elif args.cmd == "daemon":
        daemon(max_cycles=args.max_cycles)
    else:
        parser.print_help()
