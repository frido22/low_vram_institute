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

    def _render_pointer_page(self, title: str, target: str, note: str) -> str:
        return "\n".join(
            [
                f"# {title}",
                "",
                note,
                "",
                f"- Primary file: `{target}`",
            ]
        )

    def _history_rows(self) -> list[dict]:
        ledger_path = self.store.paths.public_runs_dir / "ledger.jsonl"
        if not ledger_path.exists():
            return []
        rows: list[dict] = []
        for line in ledger_path.read_text().splitlines():
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
        return rows

    def _render_history_csv(self) -> str:
        best_runs = self._history_rows()
        lines = ["run_id,score,mode,track,finished_at,title"]
        for row in best_runs:
            title = str(row.get("title", "")).replace(",", " ")
            lines.append(
                f"{row['run_id']},{row['score']:.8f},{row.get('mode','')},{row.get('track','')},{row.get('timestamp','')},{title}"
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
            run_label = row["run_id"].split("_")[-1]
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
            f'<text x="20" y="24" font-family="monospace" font-size="16" fill="#0f172a">Best Run History (lower is better)</text>'
            + "".join(y_ticks)
            + f'<line x1="{left_margin}" y1="{height - bottom_margin}" x2="{width - right_margin}" y2="{height - bottom_margin}" stroke="#94a3b8" />'
            + f'<line x1="{left_margin}" y1="{top_margin}" x2="{left_margin}" y2="{height - bottom_margin}" stroke="#94a3b8" />'
            f'<polyline fill="none" stroke="#0f766e" stroke-width="3" points="{points}" />'
            + "".join(labels)
            + f'<text x="{width / 2:.1f}" y="{height - 8}" text-anchor="middle" font-family="monospace" font-size="11" fill="#334155">Run Number</text>'
            + f'<text x="16" y="{height / 2:.1f}" text-anchor="middle" font-family="monospace" font-size="11" fill="#334155" transform="rotate(-90 16 {height / 2:.1f})">Score</text>'
            + "</svg>"
        )

    def _render_open_questions(self) -> str:
        queue = self.store.community_queue()
        lines = ["# Open Questions", ""]
        lines.append("Public suggestions are useful, but they are untrusted. Some may be weak, confused, or malicious.")
        lines.append("")
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

    def _render_overview(self, result: RunResult) -> str:
        best_runs = self.store.best_runs().get("runs", [])
        best = best_runs[0] if best_runs else None
        learning = self.store.learning_state()
        queue = self.store.community_queue()
        lines = ["# Lab Overview", ""]
        lines.append("## Latest")
        lines.append(f"- Run: {result.run_id}")
        lines.append(f"- Score: {result.evaluation.score:.4f}")
        lines.append(f"- Mode: {result.plan.mode}")
        lines.append(f"- Focus: {result.plan.title}")
        lines.append(f"- Runtime: {result.evaluation.runtime_seconds:.2f}s")
        lines.append(f"- Passed: {result.evaluation.passed}")
        lines.append(f"- Needs validation: {result.evaluation.needs_validation}")
        if result.plan.logging_focus:
            lines.append(f"- Logging focus: {', '.join(result.plan.logging_focus)}")
        lines.append("")
        lines.append("## Best")
        if best:
            lines.append(f"- Run: {best['run_id']}")
            lines.append(f"- Score: {best['score']:.4f}")
            lines.append(f"- Title: {best.get('title', 'untitled')}")
        else:
            lines.append("- No best run yet.")
        lines.append("")
        lines.append("## Learning")
        lines.append(f"- Plateau count: {learning.get('plateau_count', 0)}")
        lines.append(f"- Tested community ideas: {len(learning.get('tested_idea_titles', []))}")
        recent = learning.get("recent_runs", [])[:3]
        if recent:
            for row in recent:
                outcome = "improved" if row.get("improved_best") else "flat"
                lines.append(f"- Recent: {row['run_id']} -> {row['score']:.4f} ({outcome})")
        lines.append("")
        lines.append("## Queue")
        lines.append(f"- Open community ideas: {len(queue)}")
        lines.append("")
        lines.append("## Details")
        lines.append(f"- Full run package: `lab_public/runs/{result.run_id}/`")
        lines.append("- Best-run table: `lab_public/public/best_runs.md`")
        lines.append("- History chart: `lab_public/public/history.svg`")
        lines.append("- Open questions: `lab_public/public/open_questions.md`")
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
            f"## Logging focus\n"
            + "".join(f"- {item}\n" for item in (result.plan.logging_focus or ["score"])) + "\n"
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
        self._write_public_page("overview.md", self._render_overview(result))
        self._write_public_page("best_runs.md", self._render_best_runs())
        self._write_public_page("current_best.md", self._render_best_summary())
        self._write_public_page("open_questions.md", self._render_open_questions())
        self._write_public_page("tested_ideas.md", self._render_tested_ideas(result))
        self._write_public_page("rejected_ideas.md", self.store.rejected_ideas_text())
        self._write_public_page("history.csv", self._render_history_csv())
        self._write_public_page("history.svg", self._render_history_svg())

        self._write_public_page("current_status.md", self._render_pointer_page("Current Status", "lab_public/public/overview.md", "This file is kept for compatibility. Use the overview as the primary dashboard."))
        self._write_public_page("current_best.md", self._render_pointer_page("Current Best", "lab_public/public/overview.md", "This file is kept for compatibility. The overview and best-runs page hold the primary current-best view."))
        self._write_public_page("leaderboard.md", self._render_pointer_page("Leaderboard", "lab_public/public/best_runs.md", "This file is kept for compatibility. Use best_runs.md as the compact ranked view."))
        self._write_public_page("agenda.md", self.store.agenda_text())
        self._write_public_page("latest_thoughts.md", self._render_pointer_page("Latest Thoughts", "lab_public/runs/<run_id>/summary.md", "This file is kept for compatibility. The latest run summary is the primary source of narrative detail."))
        self._write_public_page("contributors.md", self._render_pointer_page("Contributors", "lab_public/public/tested_ideas.md", "This file is kept for compatibility. Credited idea sources appear in tested ideas and run summaries."))
        self._git_publish(result.run_id)
