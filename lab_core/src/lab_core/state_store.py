from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

from .config import Paths
from .models import RunResult


class StateStore:
    def __init__(self, paths: Paths) -> None:
        self.paths = paths
        self._ensure_layout()

    def _ensure_layout(self) -> None:
        for path in [
            self.paths.state_dir,
            self.paths.logs_dir,
            self.paths.research_dir,
            self.paths.public_root,
            self.paths.public_runs_dir,
            self.paths.public_pages_dir,
        ]:
            path.mkdir(parents=True, exist_ok=True)

    def _read_text(self, path: Path, default: str) -> str:
        return path.read_text() if path.exists() else default

    def _read_json(self, path: Path, default: Any) -> Any:
        return json.loads(path.read_text()) if path.exists() else default

    def current_state(self) -> dict[str, Any]:
        return self._read_json(self.paths.state_dir / "current_state.json", {})

    def learning_state(self) -> dict[str, Any]:
        return self._read_json(
            self.paths.state_dir / "learning_state.json",
            {
                "plateau_count": 0,
                "recent_runs": [],
                "best_score": None,
                "last_improving_run_id": None,
                "tested_idea_titles": [],
            },
        )

    def best_runs(self) -> dict[str, Any]:
        return self._read_json(
            self.paths.state_dir / "best_runs.json",
            {"best_score": None, "runs": [], "higher_is_better": True},
        )

    def agenda_text(self) -> str:
        return self._read_text(self.paths.state_dir / "agenda.md", "# Agenda\n")

    def insights_text(self) -> str:
        return self._read_text(self.paths.state_dir / "insights.md", "# Insights\n")

    def lessons_text(self) -> str:
        return self._read_text(self.paths.state_dir / "lessons.md", "# Lessons\n")

    def tactics_text(self) -> str:
        return self._read_text(self.paths.state_dir / "tactics.md", "# Tactics\n")

    def rejected_ideas_text(self) -> str:
        return self._read_text(self.paths.state_dir / "rejected_ideas.md", "# Rejected Ideas\n")

    def community_queue(self) -> list[dict[str, Any]]:
        path = self.paths.state_dir / "community_queue.jsonl"
        if not path.exists():
            return []
        rows: list[dict[str, Any]] = []
        for line in path.read_text().splitlines():
            line = line.strip()
            if line:
                rows.append(json.loads(line))
        return rows

    def _write_community_queue(self, rows: list[dict[str, Any]]) -> None:
        path = self.paths.state_dir / "community_queue.jsonl"
        content = "\n".join(json.dumps(row, sort_keys=True) for row in rows)
        path.write_text(content + ("\n" if content else ""))

    def mark_community_idea_tested(self, idea_id: str | None, status: str = "tested") -> None:
        if not idea_id:
            return
        rows = self.community_queue()
        next_rows: list[dict[str, Any]] = []
        matched = False
        for row in rows:
            if not matched and row.get("id") == idea_id:
                matched = True
                continue
            next_rows.append(row)
        self._write_community_queue(next_rows)

        if not matched:
            return

        if status == "rejected":
            rejected = self.rejected_ideas_text().rstrip()
            rejected += f"\n- {idea_id}\n"
            self.write_text("rejected_ideas.md", rejected)

    def write_json(self, rel_name: str, payload: Any) -> None:
        path = self.paths.state_dir / rel_name
        path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")

    def write_text(self, rel_name: str, content: str) -> None:
        (self.paths.state_dir / rel_name).write_text(content.rstrip() + "\n")

    def append_event(self, event_type: str, payload: dict[str, Any]) -> None:
        record = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event_type": event_type,
            "payload": payload,
        }
        with (self.paths.logs_dir / "events.jsonl").open("a") as handle:
            handle.write(json.dumps(record, sort_keys=True) + "\n")

    def write_heartbeat(self, payload: dict[str, Any]) -> None:
        (self.paths.logs_dir / "heartbeat.json").write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")

    def write_checkpoint(self, stage: str, run_id: Any = None, extra: Any = None) -> None:
        payload = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "stage": stage,
            "run_id": run_id,
            "extra": extra or {},
        }
        (self.paths.state_dir / "checkpoint.json").write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")

    def snapshot_state(self, run_id: str) -> Path:
        payload = {
            "current_state": self.current_state(),
            "best_runs": self.best_runs(),
            "learning_state": self.learning_state(),
            "agenda": self.agenda_text(),
            "insights": self.insights_text(),
            "lessons": self.lessons_text(),
            "tactics": self.tactics_text(),
            "community_queue": self.community_queue(),
        }
        snapshot_path = self.paths.logs_dir / f"{run_id}_state_snapshot.json"
        snapshot_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
        return snapshot_path

    def _render_insights(self, recent_runs: list[dict[str, Any]]) -> str:
        lines = ["# Insights", ""]
        if not recent_runs:
            lines.append("- No runs yet.")
            return "\n".join(lines)
        for row in recent_runs[:8]:
            outcome = "improved" if row.get("improved_best") else "flat"
            lines.append(f"## {row['run_id']}")
            lines.append(f"- Title: {row['title']}")
            lines.append(f"- Score: {row['score']:.4f}")
            lines.append(f"- Outcome: {outcome}")
            lines.append(f"- Needs validation: {row.get('needs_validation', False)}")
            lines.append("")
        return "\n".join(lines).rstrip()

    def _render_lessons(
        self,
        best_runs: list[dict[str, Any]],
        learning: dict[str, Any],
        queue_size: int,
    ) -> str:
        lines = ["# Lessons", ""]
        lines.append("## Current Best Pattern")
        if best_runs:
            best = best_runs[0]
            lines.append(f"- Best run: {best['run_id']}")
            lines.append(f"- Best score: {best['score']:.4f}")
            lines.append(f"- Best title: {best.get('title', 'untitled')}")
        else:
            lines.append("- No best run yet.")
        lines.append("")
        lines.append("## Working Signals")
        if best_runs:
            for row in best_runs[:3]:
                lines.append(f"- {row['title']} -> {row['score']:.4f}")
        else:
            lines.append("- No stable signals yet.")
        lines.append("")
        lines.append("## Current Risks")
        lines.append(f"- Plateau count: {learning.get('plateau_count', 0)}")
        last_improving = learning.get("last_improving_run_id") or "none"
        lines.append(f"- Last improving run: {last_improving}")
        lines.append(f"- Open community ideas: {queue_size}")
        lines.append("")
        lines.append("## Avoid Repeating")
        tested = learning.get("tested_idea_titles", [])[-5:]
        if tested:
            for title in tested:
                lines.append(f"- {title}")
        else:
            lines.append("- No tested community ideas yet.")
        return "\n".join(lines)

    def _render_tactics(self, recent_runs: list[dict[str, Any]]) -> str:
        lines = ["# Tactics", ""]
        if not recent_runs:
            lines.append("- No experiment deltas yet.")
            return "\n".join(lines)

        lines.append("## Recent Experiment Deltas")
        for row in recent_runs[:6]:
            overrides = row.get("env_overrides") or {}
            if overrides:
                delta = ", ".join(f"{key}={value}" for key, value in sorted(overrides.items()))
            else:
                delta = "no env override"
            if row.get("has_code_patch"):
                delta += " + code patch"
            outcome = "improved" if row.get("improved_best") else "flat"
            lines.append(f"- {row['run_id']}: {delta} -> {row['score']:.4f} ({outcome})")

        stats: dict[str, dict[str, int]] = {}
        for row in recent_runs:
            for key, value in (row.get("env_overrides") or {}).items():
                label = f"{key}={value}"
                entry = stats.setdefault(label, {"improved": 0, "flat": 0})
                bucket = "improved" if row.get("improved_best") else "flat"
                entry[bucket] += 1

        lines.append("")
        lines.append("## Repeated Signals")
        if not stats:
            lines.append("- No repeated env signals yet.")
            return "\n".join(lines)

        ranked = sorted(
            stats.items(),
            key=lambda item: (item[1]["improved"], -item[1]["flat"], item[0]),
            reverse=True,
        )[:8]
        for label, counts in ranked:
            verdict = "lean positive" if counts["improved"] > counts["flat"] else "unclear"
            lines.append(
                f"- {label}: improved={counts['improved']} flat={counts['flat']} -> {verdict}"
            )
        return "\n".join(lines)

    def update_after_run(self, result: RunResult) -> None:
        best_runs = self.best_runs()
        prior_best_score = best_runs.get("best_score")
        best_score = prior_best_score
        entry = {
            "run_id": result.run_id,
            "score": result.evaluation.score,
            "mode": result.plan.mode,
            "title": result.plan.title,
            "finished_at": result.finished_at,
            "track": result.plan.track,
            "runtime_seconds": result.evaluation.runtime_seconds,
            "env_overrides": dict(result.plan.env_overrides),
        }
        runs = [
            entry
        ] + [
            row
            for row in best_runs.get("runs", [])
            if row["run_id"] != result.run_id and row.get("track") == result.plan.track
        ]
        higher_is_better = result.evaluation.higher_is_better
        runs = sorted(runs, key=lambda row: row["score"], reverse=higher_is_better)[:10]
        if runs:
            best_score = runs[0]["score"]
        self.write_json("best_runs.json", {"best_score": best_score, "runs": runs, "higher_is_better": higher_is_better})

        improved_best = prior_best_score is None or (
            result.evaluation.score > prior_best_score if higher_is_better else result.evaluation.score < prior_best_score
        )

        current_state = {
            "last_run_id": result.run_id,
            "last_mode": result.plan.mode,
            "last_score": result.evaluation.score,
            "last_status": "passed" if result.evaluation.passed else "failed",
            "last_title": result.plan.title,
            "plateau_count": 0 if improved_best else self.learning_state().get("plateau_count", 0) + 1,
            "updated_at": result.finished_at,
        }
        self.write_json("current_state.json", current_state)

        agenda = (
            "# Agenda\n\n"
            f"- Current mode bias: {result.plan.mode}\n"
            f"- Latest expected signal: {result.plan.expected_signal}\n"
            f"- Next public update focus: {', '.join(result.plan.public_updates)}\n"
        )
        self.write_text("agenda.md", agenda)

        learning = self.learning_state()
        code_patch_summary = ""
        if result.plan.code_patch:
            code_patch_summary = result.plan.code_patch[:200]
        recent_runs = [
            {
                "run_id": result.run_id,
                "score": result.evaluation.score,
                "mode": result.plan.mode,
                "title": result.plan.title,
                "improved_best": improved_best,
                "needs_validation": result.evaluation.needs_validation,
                "runtime_seconds": result.evaluation.runtime_seconds,
                "env_overrides": dict(result.plan.env_overrides),
                "has_code_patch": bool(result.plan.code_patch),
                "code_patch_summary": code_patch_summary,
            }
        ] + [row for row in learning.get("recent_runs", []) if row.get("run_id") != result.run_id]
        learning.update(
            {
                "plateau_count": 0 if improved_best else learning.get("plateau_count", 0) + 1,
                "recent_runs": recent_runs[:8],
                "best_score": best_score,
                "last_improving_run_id": result.run_id if improved_best else learning.get("last_improving_run_id"),
            }
        )
        tested_titles = list(learning.get("tested_idea_titles", []))
        if result.plan.mode == "community":
            source_title = result.plan.title.removeprefix("Test community suggestion: ").strip()
            if source_title and source_title not in tested_titles:
                tested_titles.append(source_title)
            self.mark_community_idea_tested(result.plan.idea_id, status="tested" if result.evaluation.passed else "rejected")
        learning["tested_idea_titles"] = tested_titles[-20:]
        self.write_json("learning_state.json", learning)
        self.write_text("insights.md", self._render_insights(learning["recent_runs"]))
        self.write_text("lessons.md", self._render_lessons(runs, learning, len(self.community_queue())))
        self.write_text("tactics.md", self._render_tactics(learning["recent_runs"]))
