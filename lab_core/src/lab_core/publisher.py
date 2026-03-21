from __future__ import annotations

from datetime import datetime, timezone
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

    def _render_best_runs(self) -> str:
        best_runs = self.store.best_runs()
        lines = ["# Best Runs", ""]
        for row in best_runs.get("runs", []):
            title = row.get("title", "untitled")
            lines.append(f"- {row['run_id']}: {row['score']:.4f} | {row['mode']} | {title}")
        if len(lines) == 2:
            lines.append("- No best runs yet.")
        return "\n".join(lines)

    def _render_best_summary(self) -> str:
        best_runs = self.store.best_runs().get("runs", [])
        lines = ["# Current Best", ""]
        if not best_runs:
            lines.append("- No scored runs yet.")
            return "\n".join(lines)
        best = best_runs[0]
        lines.extend(
            [
                f"- Run: {best['run_id']}",
                f"- Score: {best['score']:.4f}",
                f"- Mode: {best['mode']}",
                f"- Track: {best.get('track', 'unknown')}",
                f"- Title: {best.get('title', 'untitled')}",
                f"- Finished: {best.get('finished_at', 'unknown')}",
            ]
        )
        return "\n".join(lines)

    def _render_history_csv(self) -> str:
        best_runs = self.store.best_runs().get("runs", [])
        lines = ["run_id,score,mode,track,finished_at,title"]
        for row in best_runs:
            title = str(row.get("title", "")).replace(",", " ")
            lines.append(
                f"{row['run_id']},{row['score']:.8f},{row.get('mode','')},{row.get('track','')},{row.get('finished_at','')},{title}"
            )
        return "\n".join(lines) + "\n"

    def _render_history_svg(self) -> str:
        runs = list(reversed(self.store.best_runs().get("runs", [])))
        width = 760
        height = 240
        margin = 30
        if not runs:
            return (
                f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}">'
                '<text x="20" y="40" font-family="monospace" font-size="16">No history yet.</text></svg>'
            )
        scores = [row["score"] for row in runs]
        min_score = min(scores)
        max_score = max(scores)
        if max_score == min_score:
            max_score = min_score + 1.0

        def x_for(index: int) -> float:
            if len(runs) == 1:
                return width / 2
            return margin + index * ((width - 2 * margin) / (len(runs) - 1))

        def y_for(score: float) -> float:
            ratio = (score - min_score) / (max_score - min_score)
            return height - margin - ratio * (height - 2 * margin)

        points = " ".join(f"{x_for(i):.1f},{y_for(row['score']):.1f}" for i, row in enumerate(runs))
        labels = []
        for i, row in enumerate(runs):
            labels.append(
                f'<circle cx="{x_for(i):.1f}" cy="{y_for(row["score"]):.1f}" r="4" fill="#0f766e" />'
                f'<text x="{x_for(i):.1f}" y="{height - 10}" text-anchor="middle" font-family="monospace" font-size="10">{row["run_id"].split("_")[-1]}</text>'
            )
        return (
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">'
            '<rect width="100%" height="100%" fill="#f8fafc" />'
            f'<text x="20" y="24" font-family="monospace" font-size="16" fill="#0f172a">Best Run History (lower is better)</text>'
            f'<line x1="{margin}" y1="{height - margin}" x2="{width - margin}" y2="{height - margin}" stroke="#94a3b8" />'
            f'<line x1="{margin}" y1="{margin}" x2="{margin}" y2="{height - margin}" stroke="#94a3b8" />'
            f'<polyline fill="none" stroke="#0f766e" stroke-width="3" points="{points}" />'
            + "".join(labels)
            + f'<text x="{margin}" y="{margin - 8}" font-family="monospace" font-size="10">{max(scores):.4f}</text>'
            + f'<text x="{margin}" y="{height - margin + 16}" font-family="monospace" font-size="10">{min(scores):.4f}</text>'
            + "</svg>"
        )

    def _render_open_questions(self) -> str:
        queue = self.store.community_queue()
        lines = ["# Open Questions", ""]
        for item in queue[:20]:
            author = item.get("author", "unknown")
            title = item.get("title", "untitled")
            url = item.get("url", "")
            suffix = f" ({url})" if url else ""
            lines.append(f"- [{item.get('status', 'queued')}] {title} by {author}{suffix}")
        if len(lines) == 2:
            lines.append("- No queued questions.")
        return "\n".join(lines)

    def _render_tested_ideas(self, result: RunResult) -> str:
        lines = ["# Tested Ideas", ""]
        best_runs = self.store.best_runs()
        seen_titles: set[str] = set()
        for row in best_runs.get("runs", []):
            title = row.get("title", "untitled")
            if title in seen_titles:
                continue
            seen_titles.add(title)
            lines.append(f"- {title} -> {row['run_id']} scored {row['score']:.4f}")
        lines.append("")
        lines.append("## Latest Tested Idea")
        lines.append(f"- {result.plan.title}")
        lines.append(f"- Result: {result.evaluation.score:.4f}")
        lines.append(f"- Contributor: {result.plan.idea_source or 'internal'}")
        return "\n".join(lines)

    def _git_publish(self, run_id: str) -> None:
        repo_root = self._repo_root()
        git_dir = repo_root / ".git"
        if not git_dir.exists():
            self.store.append_event("public_git_publish_skipped", {"reason": "no git repo found for publisher"})
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
            base_git + ["add", "."],
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
        candidate = self.store.paths.root
        for path in [candidate, candidate.parent, self.store.paths.public_root]:
            if (path / ".git").exists():
                return path
        return candidate

    def publish(self, result: RunResult) -> None:
        run_dir = self.store.paths.public_runs_dir / result.run_id
        run_dir.mkdir(parents=True, exist_ok=True)

        summary_md = (
            f"# {result.run_id}\n\n"
            f"## What was tried\n{result.plan.title}\n\n"
            f"## Why it was tried\n{result.plan.rationale}\n\n"
            f"## Main result\n"
            f"- Score: {result.evaluation.score:.4f}\n"
            f"- Runtime: {result.evaluation.runtime_seconds:.2f}s\n"
            f"- Passed: {result.evaluation.passed}\n"
            f"- Needs validation: {result.evaluation.needs_validation}\n\n"
            f"## What changed\n`{result.plan.adapter}` adapter run for mode `{result.plan.mode}`.\n\n"
            f"## Belief update\n{result.summary}\n\n"
            f"## What next\n{result.plan.expected_signal}\n"
        )
        (run_dir / "summary.md").write_text(summary_md)
        (run_dir / "metrics.json").write_text(
            json.dumps(
                {
                    "score": result.evaluation.score,
                    "runtime_seconds": result.evaluation.runtime_seconds,
                    "passed": result.evaluation.passed,
                    "needs_validation": result.evaluation.needs_validation,
                    "artifact_stats": result.evaluation.artifact_stats,
                },
                indent=2,
                sort_keys=True,
            )
            + "\n"
        )
        if result.outputs.get("metrics_jsonl"):
            (run_dir / "metrics.jsonl").write_text(result.outputs["metrics_jsonl"].rstrip() + "\n")
        if result.outputs.get("run_log"):
            (run_dir / "run.log").write_text(result.outputs["run_log"].rstrip() + "\n")
        if result.outputs.get("analysis_md"):
            (run_dir / "analysis.md").write_text(result.outputs["analysis_md"].rstrip() + "\n")
        (run_dir / "diff.patch").write_text(result.patch.rstrip() + "\n")
        (run_dir / "provenance.json").write_text(json.dumps(result.provenance, indent=2, sort_keys=True) + "\n")

        ledger_row = {
            "run_id": result.run_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "mode": result.plan.mode,
            "title": result.plan.title,
            "score": result.evaluation.score,
            "passed": result.evaluation.passed,
            "idea_source": result.plan.idea_source,
            "track": result.plan.track,
        }
        with (self.store.paths.public_runs_dir / "ledger.jsonl").open("a") as handle:
            handle.write(json.dumps(ledger_row, sort_keys=True) + "\n")

        best_runs = self.store.best_runs()
        leaderboard_lines = ["# Leaderboard", ""]
        for row in best_runs.get("runs", []):
            leaderboard_lines.append(f"- {row['run_id']}: {row['score']:.4f} ({row['mode']})")
        self._write_public_page("leaderboard.md", "\n".join(leaderboard_lines))
        self._write_public_page("best_runs.md", self._render_best_runs())
        self._write_public_page("current_best.md", self._render_best_summary())
        self._write_public_page("open_questions.md", self._render_open_questions())
        self._write_public_page("tested_ideas.md", self._render_tested_ideas(result))
        self._write_public_page("rejected_ideas.md", self.store.rejected_ideas_text())
        self._write_public_page("history.csv", self._render_history_csv())
        self._write_public_page("history.svg", self._render_history_svg())

        self._write_public_page(
            "current_status.md",
            (
                "# Current Status\n\n"
                f"- Latest run: {result.run_id}\n"
                f"- Mode: {result.plan.mode}\n"
                f"- Track: {result.plan.track}\n"
                f"- Score: {result.evaluation.score:.4f}\n"
                f"- Updated: {result.finished_at}\n"
            ),
        )
        self._write_public_page("agenda.md", self.store.agenda_text())
        self._write_public_page(
            "latest_thoughts.md",
            (
                "# Latest Thoughts\n\n"
                f"{result.summary}\n\n"
                "## Public Beliefs\n"
                f"{self.store.insights_text()}\n\n"
                f"Next public focus: {', '.join(result.plan.public_updates)}.\n"
            ),
        )

        contributors = "# Contributors\n\n"
        if result.plan.idea_source:
            contributors += f"- Credited idea source in latest run: {result.plan.idea_source}\n"
        else:
            contributors += "- No external contributor credited in the latest run.\n"
        self._write_public_page("contributors.md", contributors)
        self._git_publish(result.run_id)
