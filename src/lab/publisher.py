from __future__ import annotations

import base64
import json
import os
import subprocess
from datetime import datetime, timezone
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

    def _run_number(self, run_id: str) -> int:
        try:
            return int(run_id.split("_")[-1])
        except (TypeError, ValueError, AttributeError):
            return 0

    def _history_rows(self) -> list[dict]:
        """Return only runs that improved the best score (scales to 1000+ runs)."""
        ledger = self.store.ledger_rows()
        higher_is_better = self.store.best_runs().get("higher_is_better", False)
        history: list[dict] = []
        best_score: Optional[float] = None
        for row in ledger:
            score = row.get("score")
            if score is None:
                continue
            if best_score is None or (score > best_score if higher_is_better else score < best_score):
                best_score = score
                history.append(
                    {
                        "run_id": row.get("run_id", ""),
                        "score": score,
                        "mode": row.get("mode", ""),
                        "track": row.get("track", ""),
                        "finished_at": row.get("timestamp", ""),
                        "title": row.get("title", ""),
                    }
                )
        return history

    def _render_history_csv(self) -> str:
        best_runs = self._history_rows()
        lines = ["run_id,run_number,score,mode,track,finished_at,title"]
        for row in best_runs:
            title = str(row.get("title", "")).replace(",", " ")
            lines.append(
                f"{row['run_id']},{self._run_number(row['run_id'])},{row['score']:.8f},{row.get('mode','')},{row.get('track','')},{row.get('finished_at','')},{title}"
            )
        return "\n".join(lines) + "\n"

    def _render_history_svg(self) -> str:
        runs = self._history_rows()
        width = 760
        height = 280
        left_margin = 70
        right_margin = 20
        top_margin = 36
        bottom_margin = 56
        if not runs:
            return (
                f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}">'
                '<text x="20" y="40" font-family="monospace" font-size="16">No history yet.</text></svg>'
            )
        scores = [row["score"] for row in runs]
        min_score = min(scores)
        max_score = max(scores)
        if max_score == min_score:
            max_score = min_score + 0.01
        padding = max((max_score - min_score) * 0.15, 0.001)
        min_axis = min_score - padding
        max_axis = max_score + padding

        def x_for(index: int) -> float:
            if len(runs) == 1:
                return width / 2
            return left_margin + index * ((width - left_margin - right_margin) / (len(runs) - 1))

        def y_for(score: float) -> float:
            ratio = (score - min_axis) / (max_axis - min_axis)
            return height - bottom_margin - ratio * (height - top_margin - bottom_margin)

        points = " ".join(f"{x_for(i):.1f},{y_for(row['score']):.1f}" for i, row in enumerate(runs))
        labels = []
        for i, row in enumerate(runs):
            run_label = str(self._run_number(row["run_id"]))
            labels.append(
                f'<circle cx="{x_for(i):.1f}" cy="{y_for(row["score"]):.1f}" r="4" fill="#0f766e" />'
                f'<text x="{x_for(i):.1f}" y="{height - 28}" text-anchor="middle" font-family="monospace" font-size="10" fill="#334155">{run_label}</text>'
            )
        y_ticks = []
        for index in range(5):
            ratio = index / 4
            score = max_axis - ratio * (max_axis - min_axis)
            y = top_margin + ratio * (height - top_margin - bottom_margin)
            y_ticks.append(
                f'<line x1="{left_margin}" y1="{y:.1f}" x2="{width - right_margin}" y2="{y:.1f}" stroke="#e2e8f0" />'
                f'<text x="{left_margin - 8}" y="{y + 4:.1f}" text-anchor="end" font-family="monospace" font-size="10" fill="#475569">{score:.4f}</text>'
            )
        return (
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">'
            '<rect width="100%" height="100%" fill="#f8fafc" />'
            f'<text x="20" y="24" font-family="monospace" font-size="16" fill="#0f172a">Cumulative Best Score By Run (lower is better)</text>'
            + "".join(y_ticks)
            + f'<line x1="{left_margin}" y1="{height - bottom_margin}" x2="{width - right_margin}" y2="{height - bottom_margin}" stroke="#94a3b8" />'
            + f'<line x1="{left_margin}" y1="{top_margin}" x2="{left_margin}" y2="{height - bottom_margin}" stroke="#94a3b8" />'
            f'<polyline fill="none" stroke="#0f766e" stroke-width="3" points="{points}" />'
            + "".join(labels)
            + f'<text x="{width / 2:.1f}" y="{height - 8}" text-anchor="middle" font-family="monospace" font-size="11" fill="#334155">Run Number</text>'
            + f'<text x="16" y="{height / 2:.1f}" text-anchor="middle" font-family="monospace" font-size="11" fill="#334155" transform="rotate(-90 16 {height / 2:.1f})">Score</text>'
            + "</svg>"
        )

    def _render_overview(self, result: RunResult) -> str:
        best_runs = self.store.best_runs().get("runs", [])
        best = best_runs[0] if best_runs else None
        learning = self.store.learning_state()
        lines = ["# Low VRAM Institute", ""]
        lines.append("Autonomous research lab for Parameter Golf on Mac mini M4 (16GB).")
        lines.append("")
        lines.append("## Latest Run")
        lines.append(f"- **{result.run_id}**: {result.evaluation.score:.4f} ({result.plan.mode})")
        lines.append(f"- {result.plan.title}")
        lines.append(f"- Runtime: {result.evaluation.runtime_seconds:.0f}s | Passed: {result.evaluation.passed}")
        if result.plan.modified_script:
            lines.append("- Modified training script")
        lines.append("")
        lines.append("## Best")
        if best:
            lines.append(f"- **{best['score']:.4f}** ({best['run_id']}): {best.get('title', 'untitled')}")
        else:
            lines.append("- No best run yet.")
        lines.append("")
        lines.append("## Progress")
        lines.append(f"- Plateau count: {learning.get('plateau_count', 0)}")
        lines.append(f"- Total runs: {len(self.store.ledger_rows())}")
        recent = learning.get("recent_runs", [])[:5]
        for row in recent:
            outcome = "improved" if row.get("improved_best") else "flat"
            mod = " +modified" if row.get("has_modified_script") else ""
            lines.append(f"- {row['run_id']}: {row['score']:.4f} ({outcome}{mod})")
        lines.append("")
        lines.append("## Links")
        lines.append("- [Score history](history.csv) | [Chart](history.svg)")
        return "\n".join(lines)

    def _git_publish(self, run_id: str) -> None:
        repo_root = self._repo_root()
        git_dir = repo_root / ".git"
        if not git_dir.exists():
            self.store.append_event("public_git_publish_skipped", {"reason": "no git repo found"})
            return
        allowed_remote = self.runtime.get("publishing", {}).get("allowed_remote_url")
        branch = self.runtime.get("publishing", {}).get("branch", "main")
        if not self._remote_is_allowed(repo_root, allowed_remote):
            self.store.append_event("public_git_publish_skipped", {"reason": "remote not allowlisted"})
            return
        git_env = os.environ.copy()
        token = git_env.get("GITHUB_TOKEN")
        base_git = ["git"]
        if token:
            basic = base64.b64encode(f"x-access-token:{token}".encode("utf-8")).decode("ascii")
            base_git = [
                "git",
                "-c",
                "credential.helper=",
                "-c",
                "core.askPass=",
                "-c",
                f"http.extraHeader=AUTHORIZATION: basic {basic}",
            ]

        commands = [
            base_git + ["add", "output/reports", "output/runs"],
            base_git + ["commit", "-m", f"Publish {run_id}"],
            base_git + ["push", "origin", branch],
        ]
        for command in commands:
            completed = subprocess.run(  # noqa: S603
                command,
                cwd=repo_root,
                capture_output=True,
                text=True,
                check=False,
                env=git_env,
            )
            if completed.returncode != 0 and not (
                "commit" in command and "nothing to commit" in completed.stdout.lower()
            ):
                self.store.append_event(
                    "public_git_publish_failed",
                    {
                        "command": self._redact_command(command),
                        "returncode": completed.returncode,
                        "stderr": completed.stderr.strip(),
                    },
                )
                return
        self.store.append_event("public_git_publish_succeeded", {"run_id": run_id})

    def _redact_command(self, command: list[str]) -> list[str]:
        redacted: list[str] = []
        for item in command:
            if item.startswith("http.extraHeader=AUTHORIZATION: basic "):
                redacted.append("http.extraHeader=AUTHORIZATION: basic [REDACTED]")
            else:
                redacted.append(item)
        return redacted

    def _remote_is_allowed(self, repo_root, allowed_remote: Optional[str]) -> bool:
        if not allowed_remote:
            return False
        completed = subprocess.run(  # noqa: S603
            ["git", "remote", "get-url", "origin"],
            cwd=repo_root,
            capture_output=True,
            text=True,
            check=False,
        )
        if completed.returncode != 0:
            return False
        current = completed.stdout.strip()
        return current == allowed_remote

    def _repo_root(self):
        return self.store.paths.root

    def publish(self, result: RunResult) -> None:
        run_dir = self.store.paths.public_runs_dir / result.run_id
        run_dir.mkdir(parents=True, exist_ok=True)

        # Unified diff
        (run_dir / "diff.patch").write_text(result.patch.rstrip() + "\n")

        # Training log
        if result.outputs.get("run_log"):
            (run_dir / "run.log").write_text(result.outputs["run_log"].rstrip() + "\n")

        # Submission-format artifacts (Parameter Golf compatible)
        self._write_submission_artifacts(run_dir, result)

        # Metrics
        self._write_metrics_artifacts(run_dir, result)

        # Public pages: overview + history only
        self._write_public_page("overview.md", self._render_overview(result))
        self._write_public_page("history.csv", self._render_history_csv())
        self._write_public_page("history.svg", self._render_history_svg())
        self._git_publish(result.run_id)

    def _write_submission_artifacts(self, run_dir, result: RunResult) -> None:
        """Write Parameter Golf submission-format files so good runs can be submitted."""
        github_cfg = self.runtime.get("github", {})

        # submission.json — matches upstream format
        artifact_stats = result.evaluation.artifact_stats
        submission = {
            "submitter": github_cfg.get("owner", "low-vram-institute"),
            "github_id": github_cfg.get("owner", ""),
            "val_bpb": result.evaluation.score,
            "run_id": result.run_id,
            "hardware": "Apple Silicon Mac mini M4 16GB",
            "track": result.plan.track,
            "runtime_seconds": result.evaluation.runtime_seconds,
            "quantized_artifact_bytes": artifact_stats.get("quantized_artifact_bytes", 0),
            "has_modified_script": bool(result.plan.modified_script),
            "mode": result.plan.mode,
            "title": result.plan.title,
            "timestamp": result.finished_at,
        }
        (run_dir / "submission.json").write_text(
            json.dumps(submission, indent=2, sort_keys=True) + "\n"
        )

        # README.md — approach description with unified diff
        diff_section = ""
        if result.patch.strip():
            diff_section = (
                "\n## Changes\n\n"
                f"```diff\n{result.patch.strip()}\n```\n"
            )
        readme = (
            f"# {result.plan.title}\n\n"
            f"**Score:** {result.evaluation.score:.6f} val_bpb\n"
            f"**Hardware:** Apple Silicon Mac mini M4 16GB (~15 training steps in 10 min)\n"
            f"**Runtime:** {result.evaluation.runtime_seconds:.0f}s\n\n"
            f"## Approach\n\n{result.plan.rationale}\n"
            f"{diff_section}\n"
            f"## Result\n\n{result.summary}\n"
        )
        (run_dir / "README.md").write_text(readme)

        # train_gpt.py — the complete script that was actually run
        train_script = result.outputs.get("train_script", "")
        if train_script:
            (run_dir / "train_gpt.py").write_text(train_script)

    def _write_metrics_artifacts(self, run_dir, result: RunResult) -> None:
        """Write metrics.json, metrics.jsonl, and provenance.json for the run."""
        metrics = {
            "score": result.evaluation.score,
            "runtime_seconds": result.evaluation.runtime_seconds,
            "passed": result.evaluation.passed,
            "needs_validation": result.evaluation.needs_validation,
            "artifact_stats": result.evaluation.artifact_stats,
        }
        (run_dir / "metrics.json").write_text(
            json.dumps(metrics, indent=2, sort_keys=True) + "\n"
        )
        metrics_jsonl = result.outputs.get("metrics_jsonl", "")
        if metrics_jsonl:
            (run_dir / "metrics.jsonl").write_text(metrics_jsonl.rstrip() + "\n")
        if result.provenance:
            (run_dir / "provenance.json").write_text(
                json.dumps(result.provenance, indent=2, sort_keys=True) + "\n"
            )
