from __future__ import annotations

import base64
import json
import os
import subprocess
from typing import Optional

from .config import load_runtime
from .models import RunResult
from .state_store import StateStore


class Publisher:
    def __init__(self, store: StateStore) -> None:
        self.store = store
        self.runtime = load_runtime(store.paths)

    def _write_public_page(self, name: str, content: str) -> None:
        (self.store.paths.public_pages_dir / name).write_text(content.rstrip() + "\n")

    def publish(self, result: RunResult) -> None:
        run_dir = self.store.paths.public_runs_dir / result.run_id
        run_dir.mkdir(parents=True, exist_ok=True)

        # Unified diff
        (run_dir / "diff.patch").write_text(result.patch.rstrip() + "\n")

        # Training log
        if result.outputs.get("run_log"):
            (run_dir / "run.log").write_text(result.outputs["run_log"].rstrip() + "\n")

        # Submission-format artifacts
        self._write_submission_artifacts(run_dir, result)

        # Metrics
        self._write_metrics_artifacts(run_dir, result)

        # Public pages
        self._write_public_page("overview.md", self._render_overview(result))
        self._write_public_page("history.csv", self._render_history_csv())
        self._write_public_page("history.svg", self._render_history_svg())
        self._write_public_page("best_score.md", self._render_best_score())

        self._git_publish(result.run_id)

    def _write_submission_artifacts(self, run_dir, result: RunResult) -> None:
        github_cfg = self.runtime.get("github", {})
        submission = {
            "submitter": github_cfg.get("owner", "low-vram-institute"),
            "github_id": github_cfg.get("owner", ""),
            "val_bpb": result.evaluation.score,
            "run_id": result.run_id,
            "hardware": "Apple Silicon Mac mini M4 16GB",
            "track": result.plan.track,
            "runtime_seconds": result.evaluation.runtime_seconds,
            "quantized_artifact_bytes": result.evaluation.artifact_stats.get("quantized_artifact_bytes", 0),
            "has_modified_script": bool(result.plan.modified_script),
            "mode": result.plan.mode,
            "title": result.plan.title,
            "timestamp": result.finished_at,
        }
        (run_dir / "submission.json").write_text(json.dumps(submission, indent=2, sort_keys=True) + "\n")

        diff_section = ""
        if result.patch.strip():
            diff_section = f"\n## Changes\n\n```diff\n{result.patch.strip()}\n```\n"
        readme = (
            f"# {result.plan.title}\n\n"
            f"**Score:** {result.evaluation.score:.6f} val_bpb\n"
            f"**Hardware:** Apple Silicon Mac mini M4 16GB (600s wallclock)\n"
            f"**Runtime:** {result.evaluation.runtime_seconds:.0f}s\n\n"
            f"## Approach\n\n{result.plan.rationale}\n"
            f"{diff_section}\n"
            f"## Result\n\n{result.summary}\n"
        )
        (run_dir / "README.md").write_text(readme)

        train_script = result.outputs.get("train_script", "")
        if train_script:
            (run_dir / "train_gpt.py").write_text(train_script)

    def _write_metrics_artifacts(self, run_dir, result: RunResult) -> None:
        metrics = {
            "score": result.evaluation.score,
            "runtime_seconds": result.evaluation.runtime_seconds,
            "passed": result.evaluation.passed,
            "needs_validation": result.evaluation.needs_validation,
            "artifact_stats": result.evaluation.artifact_stats,
        }
        (run_dir / "metrics.json").write_text(json.dumps(metrics, indent=2, sort_keys=True) + "\n")
        metrics_jsonl = result.outputs.get("metrics_jsonl", "")
        if metrics_jsonl:
            (run_dir / "metrics.jsonl").write_text(metrics_jsonl.rstrip() + "\n")
        if result.provenance:
            (run_dir / "provenance.json").write_text(json.dumps(result.provenance, indent=2, sort_keys=True) + "\n")

    def _render_overview(self, result: RunResult) -> str:
        ledger = self.store.ledger_rows()
        best = min(ledger, key=lambda r: r["score"]) if ledger else None
        lines = [
            "# Low VRAM Institute", "",
            "Autonomous research lab for Parameter Golf on Mac mini M4 (16GB).", "",
            "## Latest Run",
            f"- **{result.run_id}**: {result.evaluation.score:.4f} ({result.plan.mode})",
            f"- {result.plan.title}",
            f"- Runtime: {result.evaluation.runtime_seconds:.0f}s | Passed: {result.evaluation.passed}",
        ]
        if result.plan.modified_script:
            lines.append("- Modified training script")
        lines.append("")
        lines.append("## Best")
        if best:
            lines.append(f"- **{best['score']:.4f}** ({best['run_id']}): {best.get('title', '')}")
        else:
            lines.append("- No runs yet.")
        lines.append("")
        lines.append(f"## Progress ({len(ledger)} runs)")
        improvements = [r for r in ledger if r.get("improved_best")]
        lines.append(f"- Improvements: {len(improvements)}")
        lines.append("")
        lines.append("## Links")
        lines.append("- [Score history](history.csv)")
        return "\n".join(lines)

    def _render_history_csv(self) -> str:
        ledger = self.store.ledger_rows()
        lines = ["run_id,score,mode,has_modified_script,improved_best,title"]
        best_so_far: Optional[float] = None
        for row in ledger:
            score = row.get("score")
            if score is None:
                continue
            improved = best_so_far is None or score < best_so_far
            if improved:
                best_so_far = score
            title = str(row.get("title", "")).replace(",", " ")
            lines.append(f"{row.get('run_id', '')},{score:.8f},{row.get('mode', '')},{row.get('has_modified_script', False)},{improved},{title}")
        return "\n".join(lines) + "\n"

    def _render_best_score(self) -> str:
        ledger = self.store.ledger_rows()
        if not ledger:
            return "# Best Score\n\nNo runs yet.\n"
        best = min(ledger, key=lambda r: r["score"])
        improvements = [r for r in ledger if r.get("improved_best")]
        lines = [
            "# Best Score", "",
            f"**{best['score']:.6f}** val_bpb", "",
            f"- Run: {best['run_id']}",
            f"- Title: {best.get('title', '')}",
            f"- Modified: {best.get('has_modified_script', False)}",
            f"- Total runs: {len(ledger)}",
            f"- Improvements: {len(improvements)}",
            "",
            "## All Improvements", "",
        ]
        for r in improvements:
            lines.append(f"- {r['run_id']} | {r['score']:.4f} | {r.get('title', '')}")
        return "\n".join(lines)

    def _render_history_svg(self) -> str:
        ledger = self.store.ledger_rows()
        # Only plot improvement points
        best_so_far: Optional[float] = None
        runs: list[dict] = []
        for row in ledger:
            score = row.get("score")
            if score is None:
                continue
            if best_so_far is None or score < best_so_far:
                best_so_far = score
                runs.append(row)

        width, height = 760, 280
        lm, rm, tm, bm = 70, 20, 36, 56
        if not runs:
            return (
                f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}">'
                '<text x="20" y="40" font-family="monospace" font-size="16">No history yet.</text></svg>'
            )
        scores = [r["score"] for r in runs]
        mn, mx = min(scores), max(scores)
        if mx == mn:
            mx = mn + 0.01
        pad = max((mx - mn) * 0.15, 0.001)
        mn_a, mx_a = mn - pad, mx + pad

        def xf(i: int) -> float:
            return width / 2 if len(runs) == 1 else lm + i * ((width - lm - rm) / (len(runs) - 1))

        def yf(s: float) -> float:
            return height - bm - ((s - mn_a) / (mx_a - mn_a)) * (height - tm - bm)

        pts = " ".join(f"{xf(i):.1f},{yf(r['score']):.1f}" for i, r in enumerate(runs))
        dots = "".join(
            f'<circle cx="{xf(i):.1f}" cy="{yf(r["score"]):.1f}" r="4" fill="#0f766e" />'
            f'<text x="{xf(i):.1f}" y="{height - 28}" text-anchor="middle" font-family="monospace" font-size="10">{r["run_id"].split("_")[-1]}</text>'
            for i, r in enumerate(runs)
        )
        ticks = "".join(
            f'<line x1="{lm}" y1="{tm + j * (height - tm - bm) / 4:.1f}" x2="{width - rm}" y2="{tm + j * (height - tm - bm) / 4:.1f}" stroke="#e2e8f0" />'
            f'<text x="{lm - 8}" y="{tm + j * (height - tm - bm) / 4 + 4:.1f}" text-anchor="end" font-family="monospace" font-size="10" fill="#475569">{mx_a - j * (mx_a - mn_a) / 4:.4f}</text>'
            for j in range(5)
        )
        return (
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}">'
            '<rect width="100%" height="100%" fill="#f8fafc" />'
            f'<text x="20" y="24" font-family="monospace" font-size="16">Best Score By Run (lower is better)</text>'
            + ticks
            + f'<polyline fill="none" stroke="#0f766e" stroke-width="3" points="{pts}" />'
            + dots + '</svg>'
        )

    # --- Git publish ---

    def _git_publish(self, run_id: str) -> None:
        repo_root = self.store.paths.root
        if not (repo_root / ".git").exists():
            return
        allowed_remote = self.runtime.get("publishing", {}).get("allowed_remote_url")
        branch = self.runtime.get("publishing", {}).get("branch", "main")
        if not self._remote_is_allowed(repo_root, allowed_remote):
            return
        git_env = os.environ.copy()
        token = git_env.get("GITHUB_TOKEN")
        base_git = ["git"]
        if token:
            basic = base64.b64encode(f"x-access-token:{token}".encode("utf-8")).decode("ascii")
            base_git = ["git", "-c", "credential.helper=", "-c", "core.askPass=",
                        "-c", f"http.extraHeader=AUTHORIZATION: basic {basic}"]
        commands = [
            base_git + ["add", "output/reports", "output/runs"],
            base_git + ["commit", "-m", f"Publish {run_id}"],
            base_git + ["push", "origin", branch],
        ]
        for command in commands:
            completed = subprocess.run(command, cwd=repo_root, capture_output=True, text=True, check=False, env=git_env)  # noqa: S603
            if completed.returncode != 0 and not ("commit" in command and "nothing to commit" in completed.stdout.lower()):
                self.store.append_event("git_publish_failed", {"command": self._redact(command), "stderr": completed.stderr.strip()})
                return
        self.store.append_event("git_publish_succeeded", {"run_id": run_id})

    def _redact(self, command: list[str]) -> list[str]:
        return ["[REDACTED]" if "AUTHORIZATION" in item else item for item in command]

    def _remote_is_allowed(self, repo_root, allowed_remote: Optional[str]) -> bool:
        if not allowed_remote:
            return False
        completed = subprocess.run(["git", "remote", "get-url", "origin"], cwd=repo_root, capture_output=True, text=True, check=False)  # noqa: S603
        return completed.returncode == 0 and completed.stdout.strip() == allowed_remote
