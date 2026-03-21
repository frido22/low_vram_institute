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

    def mark_community_idea_tested(self, title: str, status: str = "tested") -> None:
        rows = self.community_queue()
        next_rows: list[dict[str, Any]] = []
        matched = False
        for row in rows:
            row_title = row.get("title", "")
            if not matched and row_title == title:
                matched = True
                continue
            next_rows.append(row)
        self._write_community_queue(next_rows)

        if not matched:
            return

        if status == "rejected":
            rejected = self.rejected_ideas_text().rstrip()
            rejected += f"\n- {title}\n"
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
            "agenda": self.agenda_text(),
            "insights": self.insights_text(),
            "community_queue": self.community_queue(),
        }
        snapshot_path = self.paths.logs_dir / f"{run_id}_state_snapshot.json"
        snapshot_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
        return snapshot_path

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

        delta_text = "new best" if improved_best else "no improvement"
        insights = self.insights_text().rstrip() + (
            f"\n\n## {result.run_id}\n"
            f"- Hypothesis: {result.plan.title}\n"
            f"- Score: {result.evaluation.score:.4f}\n"
            f"- Outcome: {delta_text}\n"
            f"- Belief update: {result.summary}\n"
        )
        self.write_text("insights.md", insights)

        agenda = (
            "# Agenda\n\n"
            f"- Current mode bias: {result.plan.mode}\n"
            f"- Latest expected signal: {result.plan.expected_signal}\n"
            f"- Next public update focus: {', '.join(result.plan.public_updates)}\n"
        )
        self.write_text("agenda.md", agenda)

        learning = self.learning_state()
        recent_runs = [
            {
                "run_id": result.run_id,
                "score": result.evaluation.score,
                "mode": result.plan.mode,
                "title": result.plan.title,
                "improved_best": improved_best,
                "needs_validation": result.evaluation.needs_validation,
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
            self.mark_community_idea_tested(source_title, status="tested" if result.evaluation.passed else "rejected")
        learning["tested_idea_titles"] = tested_titles[-20:]
        self.write_json("learning_state.json", learning)
