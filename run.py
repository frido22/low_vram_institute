#!/usr/bin/env python3
"""Low VRAM Institute — single-file autonomous Parameter Golf runner."""
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
from urllib.request import Request, urlopen

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


def _load_sources() -> dict:
    p = CONFIG_DIR / "sources.json"
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
    rows = ledger_rows()
    if not rows:
        return "No runs yet."
    best = min(rows, key=lambda r: r["score"])
    improvements = [r for r in rows if r.get("improved_best")]
    plateau = len(rows) - max((i for i, r in enumerate(rows) if r.get("improved_best")), default=0) - 1

    lines: list[str] = []
    lines.append(f"Best: {best['score']:.4f} ({best['run_id']}) | {best.get('title', '')}")
    lines.append(f"Runs: {len(rows)} | Improvements: {len(improvements)} | Plateau streak: {plateau}")
    lines.append("")

    lines.append("Recent runs:")
    for row in rows[-15:]:
        tag = "WIN" if row.get("improved_best") else "flat"
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
        lines.append(f"- {row['run_id']} | {row['score']:.4f} | {tag} | {mod}{diag} | {row.get('title', '')}")
    lines.append("")

    failed = [r for r in rows if not r.get("improved_best") and r.get("has_modified_script")]
    if failed:
        seen: set[str] = set()
        unique: list[str] = []
        for r in reversed(failed):
            t = r.get("title", "")
            if t not in seen:
                seen.add(t)
                unique.append(f"- {t} ({r['score']:.4f})")
        lines.append(f"Failed modifications ({len(failed)} total, don't repeat):")
        lines.extend(unique[:20])
        lines.append("")

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

def _update_after_run(run_id: str, plan: dict, raw: dict) -> None:
    rows = ledger_rows()
    prior_best = min((r["score"] for r in rows), default=None)
    score = raw["score"]
    improved = prior_best is None or score < prior_best

    if improved and plan.get("modified_script"):
        _save_best(run_id, score, plan.get("title", ""), plan["modified_script"], raw["patch"])

    diag = raw.get("diagnostics", {})
    curve = _analyze_curve(raw.get("metrics_jsonl", ""))

    _append_ledger({
        "run_id": run_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "mode": plan.get("mode", ""),
        "title": plan.get("title", ""),
        "score": score,
        "passed": raw["passed"],
        "has_modified_script": bool(plan.get("modified_script")),
        "improved_best": improved,
        "runtime_seconds": raw["runtime_seconds"],
        "step_count": diag.get("step_count", 0),
        "avg_tok_s": diag.get("avg_tok_s"),
        "peak_mb": diag.get("peak_mb"),
        "active_mb": diag.get("active_mb"),
        "quantized_bytes": diag.get("quantized_bytes"),
        "curve": curve,
        "track": plan.get("track", ""),
    })

    (STATE_DIR / "current_state.json").write_text(json.dumps({
        "last_run_id": run_id,
        "last_score": score,
        "last_status": "passed" if raw["passed"] else "failed",
        "last_title": plan.get("title", ""),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }, indent=2, sort_keys=True) + "\n")


# ---------------------------------------------------------------------------
# Intake (community ideas + research)
# ---------------------------------------------------------------------------

def _load_intake() -> tuple[list[dict], list[dict]]:
    sources = _load_sources()
    community = _load_community(sources.get("github_sources", []))
    research = _load_research(sources.get("research_sources", []))
    return community, research


def _load_community(sources: list[dict]) -> list[dict]:
    rows: list[dict] = []
    for src in sources:
        if src.get("kind") == "file":
            path = (ROOT / src["path"]).resolve()
            if path.exists():
                payload = json.loads(path.read_text())
                entries = payload if isinstance(payload, list) else payload.get("items", [])
                rows.extend({
                    "id": f"github:{e['id']}", "title": e["title"],
                    "body": e.get("body", "")[:500], "author": e.get("author", "unknown"),
                } for e in entries)
        elif src.get("kind") == "github_issues":
            rows.extend(_fetch_github_issues(src))
    return rows


def _fetch_github_issues(src: dict) -> list[dict]:
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        return []
    runtime = _load_runtime()
    gh = runtime.get("github", {})
    owner = src.get("owner") or gh.get("owner", "")
    repo = src.get("repo") or gh.get("repo", "")
    if not owner or not repo:
        return []
    url = f"https://api.github.com/repos/{owner}/{repo}/issues?state=open&per_page=10"
    try:
        req = Request(url, headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "User-Agent": "low-vram-institute",
        })
        with urlopen(req, timeout=15) as resp:  # noqa: S310
            items = json.loads(resp.read().decode("utf-8"))
    except Exception:
        return []
    return [{
        "id": f"github:{it['id']}", "title": it["title"],
        "body": (it.get("body") or "")[:500],
        "author": (it.get("user") or {}).get("login", "unknown"),
    } for it in items if "pull_request" not in it]


def _load_research(sources: list[dict]) -> list[dict]:
    notes: list[dict] = []
    for src in sources:
        text = ""
        if src.get("kind") == "file":
            p = (ROOT / src["path"]).resolve()
            text = p.read_text() if p.exists() else ""
        if text.strip():
            notes.append({"title": src.get("title", src["id"]), "body": text[:3000]})
    # Upstream records
    records = ROOT / "third_party" / "parameter-golf" / "records"
    if records.exists():
        for track_dir in sorted(records.iterdir()):
            if not track_dir.is_dir():
                continue
            for readme in sorted(track_dir.glob("*/README.md")):
                try:
                    notes.append({"title": f"Upstream: {readme.parent.name}", "body": readme.read_text()[:2000]})
                except OSError:
                    continue
    return notes[:10]


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
        "required": ["mode", "title", "rationale", "expected_signal", "public_updates",
                      "adapter", "logging_focus", "idea_source", "idea_id", "modified_script"],
        "properties": {
            "mode": {"type": "string"},
            "title": {"type": "string"},
            "rationale": {"type": "string"},
            "expected_signal": {"type": "string"},
            "public_updates": {"type": "array", "items": {"type": "string"}},
            "adapter": {"type": "string", "enum": ["parameter_golf"]},
            "logging_focus": {"type": "array", "items": {"type": "string"}},
            "idea_source": {"type": ["string", "null"]},
            "idea_id": {"type": ["string", "null"]},
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
# Plan
# ---------------------------------------------------------------------------

def _build_prompt(research: list[dict], community: list[dict], run_errors: list[str] | None = None) -> str:
    runtime = _load_runtime()
    track = runtime.get("parameter_golf", {}).get("local_track", "mac_mini_official_like")

    # Rules
    rules_path = CONFIG_DIR / "parameter_golf_rules.md"
    rules = rules_path.read_text().strip() if rules_path.exists() else ""

    # Training script
    ws_path = runtime.get("parameter_golf", {}).get("workspace", "")
    script_path = Path(ws_path) / "train_gpt_mlx.py" if ws_path else None
    script = "(script not available)"
    if script_path and script_path.exists():
        try:
            script = script_path.read_text()
        except OSError:
            pass

    ctx = render_context()
    diff = best_diff().strip()
    diff_section = f"## Current Best Changes\n```diff\n{diff}\n```\n\n" if diff else ""

    # Format helpers
    def fmt_community(items: list[dict]) -> str:
        if not items:
            return "- none"
        return "\n".join(f"- @{it.get('author', '?')}: {it.get('title', 'untitled')}" for it in items[:5])

    def fmt_research(items: list[dict]) -> str:
        if not items:
            return "- none"
        lines = []
        for n in items[:3]:
            body = " ".join(str(n.get("body", "")).split())
            if len(body) > 400:
                body = body[:397] + "..."
            lines.append(f"- {n.get('title', 'untitled')}: {body}")
        return "\n".join(lines)

    prompt = (
        "You are the autonomous planner for a public research lab on a Mac mini M4 (16GB).\n"
        "Return only JSON matching the provided schema.\n\n"
        "## Modes\n"
        "- explore: baselines (only when no data exists)\n"
        "- exploit: compound on current best\n"
        "- research: try something new\n"
        "- community: test an external suggestion\n\n"
        "## Output\n"
        "Return `modified_script`: the COMPLETE modified `train_gpt_mlx.py`.\n"
        "EVERY run must change something. Null is only acceptable for the very first baseline.\n"
        "To compound: incorporate the best diff below and add your changes.\n"
        "Original is always restored after each run — be fearless.\n\n"
        f"{rules}\n\n"
        "## Run History\n"
        f"{ctx}\n\n"
        f"{diff_section}"
        "## Community Ideas\n"
        f"{fmt_community(community)}\n\n"
        "## Research Notes\n"
        f"{fmt_research(research)}\n\n"
        "## Original train_gpt_mlx.py\n\n"
        f"```python\n{script}\n```\n"
    )
    if run_errors:
        prompt += "\n## Previous Run Errors\n\nFix the issue or try a different approach.\n\n"
        for i, err in enumerate(run_errors):
            prompt += f"- Attempt {i + 1}: {err}\n"
    return prompt


def plan(research: list[dict], community: list[dict], run_errors: list[str] | None = None) -> dict:
    runtime = _load_runtime()
    codex_cfg = runtime.get("codex", {})
    track = runtime.get("parameter_golf", {}).get("local_track", "mac_mini_official_like")

    if codex_cfg.get("enabled"):
        prompt = _build_prompt(research, community, run_errors)
        payload = _call_codex(prompt, model=codex_cfg.get("model"))
        return {
            "mode": payload["mode"],
            "title": payload["title"],
            "rationale": payload["rationale"],
            "expected_signal": payload["expected_signal"],
            "modified_script": payload.get("modified_script") or None,
            "track": track,
            "idea_source": payload.get("idea_source"),
            "idea_id": payload.get("idea_id"),
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
# Publishing (CSV, SVG, run artifacts, git push)
# ---------------------------------------------------------------------------

def _publish(run_id: str, plan_dict: dict, raw: dict) -> None:
    run_dir = RUNS_DIR / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    # Run artifacts
    (run_dir / "diff.patch").write_text((raw.get("patch") or "").rstrip() + "\n")
    if raw.get("run_log"):
        (run_dir / "run.log").write_text(raw["run_log"].rstrip() + "\n")
    if raw.get("train_script"):
        (run_dir / "train_gpt.py").write_text(raw["train_script"])
    if raw.get("metrics_jsonl"):
        (run_dir / "metrics.jsonl").write_text(raw["metrics_jsonl"].rstrip() + "\n")
    if raw.get("provenance"):
        (run_dir / "provenance.json").write_text(json.dumps(raw["provenance"], indent=2, sort_keys=True) + "\n")

    # Submission JSON
    runtime = _load_runtime()
    owner = runtime.get("github", {}).get("owner", "low-vram-institute")
    (run_dir / "submission.json").write_text(json.dumps({
        "submitter": owner, "github_id": owner,
        "val_bpb": raw["score"], "run_id": run_id,
        "hardware": "Apple Silicon Mac mini M4 16GB",
        "track": plan_dict.get("track", ""),
        "runtime_seconds": raw["runtime_seconds"],
        "quantized_artifact_bytes": raw.get("diagnostics", {}).get("quantized_bytes", 0),
        "has_modified_script": bool(plan_dict.get("modified_script")),
        "mode": plan_dict.get("mode", ""),
        "title": plan_dict.get("title", ""),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }, indent=2, sort_keys=True) + "\n")

    # Metrics JSON
    (run_dir / "metrics.json").write_text(json.dumps({
        "score": raw["score"], "runtime_seconds": raw["runtime_seconds"],
        "passed": raw["passed"],
    }, indent=2, sort_keys=True) + "\n")

    # README
    patch = (raw.get("patch") or "").strip()
    diff_section = f"\n## Changes\n\n```diff\n{patch}\n```\n" if patch else ""
    (run_dir / "README.md").write_text(
        f"# {plan_dict.get('title', run_id)}\n\n"
        f"**Score:** {raw['score']:.6f} val_bpb\n"
        f"**Hardware:** Apple Silicon Mac mini M4 16GB (600s wallclock)\n"
        f"**Runtime:** {raw['runtime_seconds']:.0f}s\n\n"
        f"## Approach\n\n{plan_dict.get('rationale', '')}\n"
        f"{diff_section}\n"
        f"## Result\n\n{raw['summary']}\n"
    )

    # Reports
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    _write_report("overview.md", _render_overview(run_id, plan_dict, raw))
    _write_report("history.csv", _render_history_csv())
    _write_report("history.svg", _render_history_svg())
    _write_report("best_score.md", _render_best_score())

    _git_push(run_id)


def _write_report(name: str, content: str) -> None:
    (REPORTS_DIR / name).write_text(content.rstrip() + "\n")


def _render_overview(run_id: str, plan_dict: dict, raw: dict) -> str:
    rows = ledger_rows()
    best = min(rows, key=lambda r: r["score"]) if rows else None
    improvements = [r for r in rows if r.get("improved_best")]
    lines = [
        "# Low VRAM Institute", "",
        "Autonomous research lab for Parameter Golf on Mac mini M4 (16GB).", "",
        "## Latest Run",
        f"- **{run_id}**: {raw['score']:.4f} ({plan_dict.get('mode', '')})",
        f"- {plan_dict.get('title', '')}",
        f"- Runtime: {raw['runtime_seconds']:.0f}s | Passed: {raw['passed']}",
    ]
    if plan_dict.get("modified_script"):
        lines.append("- Modified training script")
    lines.append("")
    lines.append("## Best")
    if best:
        lines.append(f"- **{best['score']:.4f}** ({best['run_id']}): {best.get('title', '')}")
    lines.append("")
    lines.append(f"## Progress ({len(rows)} runs)")
    lines.append(f"- Improvements: {len(improvements)}")
    lines.append("")
    lines.append("## Links")
    lines.append("- [Score history](history.csv)")
    return "\n".join(lines)


def _render_history_csv() -> str:
    rows = ledger_rows()
    lines = ["run_id,score,mode,has_modified_script,improved_best,title"]
    best_so_far: float | None = None
    for row in rows:
        score = row.get("score")
        if score is None:
            continue
        improved = best_so_far is None or score < best_so_far
        if improved:
            best_so_far = score
        title = str(row.get("title", "")).replace(",", " ")
        lines.append(f"{row.get('run_id', '')},{score:.8f},{row.get('mode', '')},{row.get('has_modified_script', False)},{improved},{title}")
    return "\n".join(lines) + "\n"


def _render_best_score() -> str:
    rows = ledger_rows()
    if not rows:
        return "# Best Score\n\nNo runs yet.\n"
    best = min(rows, key=lambda r: r["score"])
    improvements = [r for r in rows if r.get("improved_best")]
    lines = [
        "# Best Score", "",
        f"**{best['score']:.6f}** val_bpb", "",
        f"- Run: {best['run_id']}",
        f"- Title: {best.get('title', '')}",
        f"- Modified: {best.get('has_modified_script', False)}",
        f"- Total runs: {len(rows)}",
        f"- Improvements: {len(improvements)}",
        "", "## All Improvements", "",
    ]
    for r in improvements:
        lines.append(f"- {r['run_id']} | {r['score']:.4f} | {r.get('title', '')}")
    return "\n".join(lines)


def _render_history_svg() -> str:
    rows = ledger_rows()
    best_so_far: float | None = None
    pts_data: list[dict] = []
    for row in rows:
        score = row.get("score")
        if score is None:
            continue
        if best_so_far is None or score < best_so_far:
            best_so_far = score
            pts_data.append(row)

    w, h = 760, 280
    lm, rm, tm, bm = 70, 20, 36, 56
    if not pts_data:
        return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}">'
                '<text x="20" y="40" font-family="monospace" font-size="16">No history yet.</text></svg>')

    scores = [r["score"] for r in pts_data]
    mn, mx = min(scores), max(scores)
    if mx == mn:
        mx = mn + 0.01
    pad = max((mx - mn) * 0.15, 0.001)
    mn_a, mx_a = mn - pad, mx + pad

    def xf(i: int) -> float:
        return w / 2 if len(pts_data) == 1 else lm + i * ((w - lm - rm) / (len(pts_data) - 1))

    def yf(s: float) -> float:
        return h - bm - ((s - mn_a) / (mx_a - mn_a)) * (h - tm - bm)

    pts = " ".join(f"{xf(i):.1f},{yf(r['score']):.1f}" for i, r in enumerate(pts_data))
    dots = "".join(
        f'<circle cx="{xf(i):.1f}" cy="{yf(r["score"]):.1f}" r="4" fill="#0f766e" />'
        f'<text x="{xf(i):.1f}" y="{h - 28}" text-anchor="middle" font-family="monospace" font-size="10">{r["run_id"].split("_")[-1]}</text>'
        for i, r in enumerate(pts_data)
    )
    ticks = "".join(
        f'<line x1="{lm}" y1="{tm + j * (h - tm - bm) / 4:.1f}" x2="{w - rm}" y2="{tm + j * (h - tm - bm) / 4:.1f}" stroke="#e2e8f0" />'
        f'<text x="{lm - 8}" y="{tm + j * (h - tm - bm) / 4 + 4:.1f}" text-anchor="end" font-family="monospace" font-size="10" fill="#475569">{mx_a - j * (mx_a - mn_a) / 4:.4f}</text>'
        for j in range(5)
    )
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}">'
        '<rect width="100%" height="100%" fill="#f8fafc" />'
        f'<text x="20" y="24" font-family="monospace" font-size="16">Best Score By Run (lower is better)</text>'
        + ticks
        + f'<polyline fill="none" stroke="#0f766e" stroke-width="3" points="{pts}" />'
        + dots + '</svg>'
    )


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
            _emit(f"git push failed: {r.stderr.strip()[:200]}")
            return


# ---------------------------------------------------------------------------
# Run lock
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


# ---------------------------------------------------------------------------
# Run ID
# ---------------------------------------------------------------------------

def _next_run_id() -> str:
    prefix = datetime.now(timezone.utc).strftime("%Y_%m_%d_run_")
    existing = [p.name for p in RUNS_DIR.iterdir() if p.is_dir() and p.name.startswith(prefix)] if RUNS_DIR.exists() else []
    return prefix + f"{len(existing) + 1:04d}"


# ---------------------------------------------------------------------------
# Core loop
# ---------------------------------------------------------------------------

def run_once() -> str:
    usage = shutil.disk_usage(ROOT)
    if usage.free < MIN_FREE_DISK:
        raise RuntimeError("Low disk space.")

    runtime = _load_runtime()
    pg_config = runtime.get("parameter_golf", {})

    with _run_lock():
        run_id = _next_run_id()
        _emit(f"starting {run_id}")

        community, research = _load_intake()
        _emit(f"intake: {len(community)} community, {len(research)} research")

        run_errors: list[str] = []
        for attempt in range(3):
            p = plan(research, community, run_errors=run_errors or None)
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


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Low VRAM Institute runner")
    sub = parser.add_subparsers(dest="command")
    sub.add_parser("run-once", help="Run a single cycle")
    d = sub.add_parser("daemon", help="Run continuously")
    d.add_argument("--max-cycles", type=int, default=None)
    args = parser.parse_args()

    for d in [STATE_DIR, LOGS_DIR, RUNS_DIR, REPORTS_DIR]:
        d.mkdir(parents=True, exist_ok=True)

    if args.command == "run-once":
        run_once()
    elif args.command == "daemon":
        daemon(max_cycles=args.max_cycles)
    else:
        parser.print_help()
