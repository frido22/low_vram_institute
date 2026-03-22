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

# ---------------------------------------------------------------------------
# Paths & constants
# ---------------------------------------------------------------------------

ROOT = Path(__file__).resolve().parent
STATE_DIR = ROOT / "state"
LOGS_DIR = ROOT / "logs"
CONFIG_DIR = ROOT / "config"
RUNS_DIR = ROOT / "output" / "runs"
REPORTS_DIR = ROOT / "output" / "reports"

HEARTBEAT_S = 10
BASE_BACKOFF = 10
MAX_BACKOFF = 300
MIN_FREE_DISK = 2_000_000_000
STALE_LOCK_S = 3600


def _emit(msg: str) -> None:
    print(f"[lab] {msg}", flush=True)


def _load_runtime() -> dict[str, Any]:
    p = CONFIG_DIR / "runtime.json"
    return json.loads(p.read_text()) if p.exists() else {}


# ---------------------------------------------------------------------------
# Ledger (state/ledger.jsonl)
# ---------------------------------------------------------------------------

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


def best_diff() -> str:
    p = STATE_DIR / "best_diff.patch"
    return p.read_text() if p.exists() else ""


def _save_best(run_id: str, score: float, title: str, script: str, patch: str) -> None:
    (STATE_DIR / "best_script.json").write_text(json.dumps({
        "run_id": run_id, "score": score, "title": title, "modified_script": script,
    }, indent=2, sort_keys=True) + "\n")
    (STATE_DIR / "best_diff.patch").write_text(patch.rstrip() + "\n")


# ---------------------------------------------------------------------------
# Curve analysis
# ---------------------------------------------------------------------------

def _analyze_curve(metrics_jsonl: str) -> str:
    if not metrics_jsonl:
        return "no_data"
    scores = []
    for line in metrics_jsonl.strip().splitlines():
        try:
            row = json.loads(line.strip())
            scores.append(row.get("val_bpb", row.get("val_loss", 0)))
        except (json.JSONDecodeError, ValueError):
            continue
    if len(scores) < 2:
        return "too_short"
    mid = len(scores) // 2
    early = scores[0] - scores[mid]
    late = scores[mid] - scores[-1]
    if early > 0.001 and late > 0.001:
        return "improving"
    if early > 0.001:
        return "plateaued"
    if late > 0.001:
        return "slow_start"
    return "flat"


# ---------------------------------------------------------------------------
# Render context for prompt (the memory system)
# ---------------------------------------------------------------------------

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

    # 2. Recent runs with diagnostics + delta
    lines.append("Recent runs:")
    for row in rows[-15:]:
        delta = row["score"] - best_val
        tag = "WIN" if row.get("improved_best") else f"+{delta:.4f}"
        mod = "mod" if row.get("has_modified_script") else "base"
        parts = []
        if row.get("step_count"):
            parts.append(f"{row['step_count']}steps")
        if row.get("runtime_seconds"):
            parts.append(f"{row['runtime_seconds']:.0f}s")
        if row.get("avg_tok_s"):
            parts.append(f"{row['avg_tok_s']:.0f}tok/s")
        if row.get("peak_mb"):
            parts.append(f"{row['peak_mb']:.0f}MB")
        if row.get("curve") and row["curve"] != "no_data":
            parts.append(row["curve"])
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

    # 5. Improvement path — how we got to current best
    if improvements:
        lines.append("Improvements (path to current best):")
        for r in improvements:
            mod = "+script" if r.get("has_modified_script") else "baseline"
            lines.append(f"- {r['run_id']} {r['score']:.4f} [{mod}] {r.get('title', '')}")
        lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Update state after run
# ---------------------------------------------------------------------------

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
        "mode": plan_dict.get("mode", ""),
        "title": plan_dict.get("title", ""),
        "rationale": plan_dict.get("rationale", ""),
        "score": score,
        "passed": raw["passed"],
        "has_modified_script": bool(plan_dict.get("modified_script")),
        "improved_best": improved,
        "runtime_seconds": raw["runtime_seconds"],
        "step_count": diag.get("step_count", 0),
        "avg_tok_s": diag.get("avg_tok_s"),
        "peak_mb": diag.get("peak_mb"),
        "active_mb": diag.get("active_mb"),
        "quantized_bytes": diag.get("quantized_bytes"),
        "curve": curve,
        "track": plan_dict.get("track", ""),
    })


# ---------------------------------------------------------------------------
# Codex (planning)
# ---------------------------------------------------------------------------

class CodexError(RuntimeError):
    def __init__(self, msg: str, retryable: bool = True) -> None:
        super().__init__(msg)
        self.retryable = retryable


def _call_codex(prompt: str, model: str | None = None) -> dict:
    binary = shutil.which("codex")
    if not binary:
        raise CodexError("Codex CLI not found in PATH.")

    schema = {
        "type": "object",
        "required": ["mode", "title", "rationale", "expected_signal", "modified_script"],
        "properties": {
            "mode": {"type": "string"},
            "title": {"type": "string"},
            "rationale": {"type": "string"},
            "expected_signal": {"type": "string"},
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


# ---------------------------------------------------------------------------
# Plan (prompt from config/prompt.md template)
# ---------------------------------------------------------------------------

def _build_prompt(run_errors: list[str] | None = None) -> str:
    runtime = _load_runtime()

    # Template
    template_path = CONFIG_DIR / "prompt.md"
    template = template_path.read_text() if template_path.exists() else "Return a plan as JSON.\n{rules}\n{history}\n{script}\n"

    # Rules
    rules_path = CONFIG_DIR / "parameter_golf_rules.md"
    rules = rules_path.read_text().strip() if rules_path.exists() else ""

    # Training script
    ws_path = runtime.get("parameter_golf", {}).get("workspace", "")
    script = "(script not available)"
    if ws_path:
        sp = Path(ws_path) / "train_gpt_mlx.py"
        if sp.exists():
            try:
                script = sp.read_text()
            except OSError:
                pass

    # Best diff
    diff = best_diff().strip()
    diff_section = f"## Current Best Changes\n```diff\n{diff}\n```" if diff else ""

    # Errors
    errors_section = ""
    if run_errors:
        errors_section = "## Previous Run Errors\n\nFix the issue or try a different approach.\n\n"
        for i, err in enumerate(run_errors):
            errors_section += f"- Attempt {i + 1}: {err}\n"

    return template.format(
        rules=rules,
        history=render_context(),
        best_diff_section=diff_section,
        script=script,
        errors_section=errors_section,
    )


def plan(run_errors: list[str] | None = None) -> dict:
    runtime = _load_runtime()
    codex_cfg = runtime.get("codex", {})
    track = runtime.get("parameter_golf", {}).get("local_track", "mac_mini_official_like")

    if codex_cfg.get("enabled"):
        prompt = _build_prompt(run_errors)
        payload = _call_codex(prompt, model=codex_cfg.get("model"))
        return {
            "mode": payload["mode"],
            "title": payload["title"],
            "rationale": payload["rationale"],
            "expected_signal": payload["expected_signal"],
            "modified_script": payload.get("modified_script") or None,
            "track": track,
        }

    # Heuristic fallback
    mode = "explore" if best_score() is None else "exploit"
    return {
        "mode": mode,
        "title": "Establish baseline" if mode == "explore" else "Refine current best",
        "rationale": "Baseline needed." if mode == "explore" else "Exploiting current best.",
        "expected_signal": "First score." if mode == "explore" else "Score delta.",
        "modified_script": best_script() if mode == "exploit" else None,
        "track": track,
    }


# ---------------------------------------------------------------------------
# Publish (per-run artifacts + CSV + SVG + git push)
# ---------------------------------------------------------------------------

def _publish(run_id: str, plan_dict: dict, raw: dict) -> None:
    run_dir = RUNS_DIR / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    # Per-run artifacts
    (run_dir / "diff.patch").write_text((raw.get("patch") or "").rstrip() + "\n")
    if raw.get("run_log"):
        (run_dir / "run.log").write_text(raw["run_log"].rstrip() + "\n")
    if raw.get("metrics_jsonl"):
        (run_dir / "metrics.jsonl").write_text(raw["metrics_jsonl"].rstrip() + "\n")

    # Submission JSON (Parameter Golf format)
    runtime = _load_runtime()
    owner = runtime.get("github", {}).get("owner", "low-vram-institute")
    (run_dir / "submission.json").write_text(json.dumps({
        "submitter": owner, "val_bpb": raw["score"], "run_id": run_id,
        "hardware": "Mac mini M4 16GB", "track": plan_dict.get("track", ""),
        "runtime_seconds": raw["runtime_seconds"],
        "has_modified_script": bool(plan_dict.get("modified_script")),
        "title": plan_dict.get("title", ""),
    }, indent=2, sort_keys=True) + "\n")

    # Reports
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    (REPORTS_DIR / "history.csv").write_text(_render_csv())
    (REPORTS_DIR / "history.svg").write_text(_render_svg())

    _git_push(run_id)


def _render_csv() -> str:
    rows = ledger_rows()
    lines = ["run_id,score,mode,modified,improved,title"]
    best_so_far: float | None = None
    for row in rows:
        score = row.get("score")
        if score is None:
            continue
        improved = best_so_far is None or score < best_so_far
        if improved:
            best_so_far = score
        title = str(row.get("title", "")).replace(",", " ")
        lines.append(f"{row.get('run_id', '')},{score:.6f},{row.get('mode', '')},{row.get('has_modified_script', False)},{improved},{title}")
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


# ---------------------------------------------------------------------------
# Git push
# ---------------------------------------------------------------------------

def _git_push(run_id: str) -> None:
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

    for cmd in [
        base + ["add", "output/reports", "output/runs"],
        base + ["commit", "-m", f"Publish {run_id}"],
        base + ["push", "origin", branch],
    ]:
        r = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, check=False)  # noqa: S603
        if r.returncode != 0 and not ("commit" in cmd and "nothing to commit" in r.stdout.lower()):
            _emit(f"git failed: {r.stderr.strip()[:200]}")
            return


# ---------------------------------------------------------------------------
# Core loop
# ---------------------------------------------------------------------------

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
            _emit(f"plan {p.get('mode', '?')}: {p.get('title', '?')}")

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
