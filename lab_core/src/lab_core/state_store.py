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
        best_score = best_runs.get("best_score")
        entry = {
            "run_id": result.run_id,
            "score": result.evaluation.score,
            "mode": result.plan.mode,
            "title": result.plan.title,
            "finished_at": result.finished_at,
            "track": result.plan.track,
        }
        runs = [entry] + [row for row in best_runs.get("runs", []) if row["run_id"] != result.run_id]
        higher_is_better = result.evaluation.higher_is_better
        runs = sorted(runs, key=lambda row: row["score"], reverse=higher_is_better)[:10]
        if runs:
            best_score = runs[0]["score"]
        self.write_json("best_runs.json", {"best_score": best_score, "runs": runs, "higher_is_better": higher_is_better})

        current_state = {
            "last_run_id": result.run_id,
            "last_mode": result.plan.mode,
            "last_score": result.evaluation.score,
            "last_status": "passed" if result.evaluation.passed else "failed",
            "updated_at": result.finished_at,
        }
        self.write_json("current_state.json", current_state)

        insights = self.insights_text().rstrip() + (
            f"\n\n## {result.run_id}\n"
            f"- Hypothesis: {result.plan.title}\n"
            f"- Score: {result.evaluation.score:.4f}\n"
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
