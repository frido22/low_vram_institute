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
        self._write_public_page("open_questions.md", self._render_open_questions())
        self._write_public_page("tested_ideas.md", self._render_tested_ideas(result))
        self._write_public_page("rejected_ideas.md", self.store.rejected_ideas_text())

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
