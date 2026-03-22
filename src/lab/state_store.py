from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

from .config import Paths
from .models import COMMUNITY_TITLE_PREFIX, RunResult


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

    # --- Core state readers ---

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

    def lessons_text(self) -> str:
        return self._read_text(self.paths.state_dir / "lessons.md", "# Lessons\n")

    def rejected_ideas_text(self) -> str:
        return self._read_text(self.paths.state_dir / "rejected_ideas.md", "# Rejected Ideas\n")

    def best_script(self) -> str | None:
        """Return the full modified script from the current best run, or None."""
        data = self._read_json(self.paths.state_dir / "best_script.json", None)
        if isinstance(data, dict):
            return data.get("modified_script")
        return None

    def best_diff(self) -> str:
        """Unified diff of the current best changes vs original."""
        return self._read_text(self.paths.state_dir / "best_diff.patch", "")

    # --- Ledger ---

    def ledger_rows(self) -> list[dict[str, Any]]:
        path = self.paths.state_dir / "ledger.jsonl"
        if not path.exists():
            return []
        rows: list[dict[str, Any]] = []
        for line in path.read_text().splitlines():
            line = line.strip()
            if line:
                rows.append(json.loads(line))
        return rows

    def append_ledger(self, row: dict[str, Any]) -> None:
        with (self.paths.state_dir / "ledger.jsonl").open("a") as handle:
            handle.write(json.dumps(row, sort_keys=True) + "\n")

    # --- Community queue ---

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

    # --- Writers ---

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
            "lessons": self.lessons_text(),
            "community_queue": self.community_queue(),
        }
        snapshot_path = self.paths.logs_dir / f"{run_id}_state_snapshot.json"
        snapshot_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
        return snapshot_path

    # --- Best script memory ---

    def save_best_script(self, result: RunResult) -> None:
        """Save a winning run's modified script and its unified diff."""
        if not result.plan.modified_script:
            return
        self.write_json("best_script.json", {
            "run_id": result.run_id,
            "score": result.evaluation.score,
            "title": result.plan.title,
            "modified_script": result.plan.modified_script,
        })
        # The diff is stored in result.patch (computed by the adapter)
        self.write_text("best_diff.patch", result.patch)

    # --- Lessons rendering ---

    def _render_lessons(
        self,
        best_runs: list[dict[str, Any]],
        learning: dict[str, Any],
        recent_runs: list[dict[str, Any]],
        result: RunResult | None = None,
        improved_best: bool = False,
    ) -> str:
        lines = ["# Lessons", ""]

        # Current best
        if best_runs:
            best = best_runs[0]
            lines.append(f"Best: {best['run_id']} {best['score']:.4f} | {best.get('title', 'untitled')}")
        else:
            lines.append("Best: none yet")
        lines.append("")

        # Hardware context
        lines.append("## Hardware Reality")
        lines.append("- Mac mini M4 16GB does ~15 training steps in 10 minutes")
        lines.append("- Every technique must be evaluated through the lens of: does this help with only 15 gradient updates?")
        lines.append("- Upstream H100 techniques may not transfer — always ask why before trying")
        lines.append("")

        # Best diff reference
        best_diff = self.best_diff().strip()
        if best_diff:
            lines.append("## Current Best Changes (unified diff)")
            lines.append(f"```diff\n{best_diff}\n```")
            lines.append("")

        # Causal insights (preserved across runs)
        existing = self._read_text(self.paths.state_dir / "insights.md", "").strip()
        if result and improved_best and result.plan.modified_script:
            new_insight = (
                f"- **{result.run_id}** ({result.evaluation.score:.4f}): "
                f"{result.plan.title} — IMPROVED."
            )
            existing = (existing + "\n" + new_insight).strip()
            self.write_text("insights.md", existing)
        if existing:
            lines.append("## What Worked (causal insights)")
            lines.append(existing)
            lines.append("")

        # Failed hypotheses
        if result and not improved_best and result.plan.modified_script:
            failed = self._read_text(self.paths.state_dir / "failed.md", "").strip()
            new_fail = (
                f"- **{result.run_id}** ({result.evaluation.score:.4f}): "
                f"{result.plan.title} — FLAT/REGRESSED."
            )
            failed = (failed + "\n" + new_fail).strip()
            # Keep last 20 failures
            fail_lines = failed.splitlines()
            if len(fail_lines) > 20:
                failed = "\n".join(fail_lines[-20:])
            self.write_text("failed.md", failed)

        failed_text = self._read_text(self.paths.state_dir / "failed.md", "").strip()
        if failed_text:
            lines.append("## What Failed (do not repeat)")
            lines.append(failed_text)
            lines.append("")

        # Idea categories tested
        lines.append("## Idea Categories Explored")
        categories = self._count_categories(recent_runs + [r for r in best_runs])
        for cat, count in sorted(categories.items()):
            lines.append(f"- {cat}: {count} runs")
        lines.append("")

        # Recent experiment deltas
        lines.append("## Recent Runs")
        if recent_runs:
            for row in recent_runs[:12]:
                mod_tag = "modified" if row.get("has_modified_script") else "baseline"
                outcome = "improved" if row.get("improved_best") else "flat"
                lines.append(f"- {row['run_id']}: {row['score']:.4f} ({outcome}) [{mod_tag}] {row.get('title', '')}")
        else:
            lines.append("- none")
        lines.append("")

        # Tested community ideas
        tested = learning.get("tested_idea_titles", [])[-5:]
        if tested:
            lines.append("## Tested Ideas (avoid repeating)")
            for title in tested:
                lines.append(f"- {title}")

        return "\n".join(lines)

    def _count_categories(self, runs: list[dict[str, Any]]) -> dict[str, int]:
        """Categorize runs by what they changed."""
        categories: dict[str, int] = {}
        for run in runs:
            title = run.get("title", "").lower()
            if any(w in title for w in ["warmdown", "warmup", "schedule", "lr", "learning rate", "cosine"]):
                cat = "schedule"
            elif any(w in title for w in ["bigram", "smeargate", "mlp", "layer", "depth", "architecture", "residual", "embed"]):
                cat = "architecture"
            elif any(w in title for w in ["quantiz", "int5", "int6", "int8", "compress", "zlib", "zstd"]):
                cat = "quantization"
            elif any(w in title for w in ["muon", "adam", "momentum", "weight decay", "wd", "optimizer"]):
                cat = "optimizer"
            elif any(w in title for w in ["eval", "valid", "sliding", "window"]):
                cat = "evaluation"
            elif any(w in title for w in ["swa", "averaging", "ema"]):
                cat = "weight_averaging"
            elif any(w in title for w in ["replay", "confirm", "re-run"]):
                cat = "validation"
            else:
                cat = "other"
            categories[cat] = categories.get(cat, 0) + 1
        return categories

    # --- Main update ---

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

        # Save winning script
        if improved_best and result.plan.modified_script:
            self.save_best_script(result)

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

        learning = self.learning_state()
        recent_runs = [
            {
                "run_id": result.run_id,
                "score": result.evaluation.score,
                "mode": result.plan.mode,
                "title": result.plan.title,
                "improved_best": improved_best,
                "needs_validation": result.evaluation.needs_validation,
                "runtime_seconds": result.evaluation.runtime_seconds,
                "has_modified_script": bool(result.plan.modified_script),
            }
        ] + [row for row in learning.get("recent_runs", []) if row.get("run_id") != result.run_id]
        learning.update(
            {
                "plateau_count": 0 if improved_best else learning.get("plateau_count", 0) + 1,
                "recent_runs": recent_runs[:12],
                "best_score": best_score,
                "last_improving_run_id": result.run_id if improved_best else learning.get("last_improving_run_id"),
            }
        )
        tested_titles = list(learning.get("tested_idea_titles", []))
        if result.plan.mode == "community":
            source_title = result.plan.title.removeprefix(COMMUNITY_TITLE_PREFIX).strip()
            if source_title and source_title not in tested_titles:
                tested_titles.append(source_title)
            self.mark_community_idea_tested(result.plan.idea_id, status="tested" if result.evaluation.passed else "rejected")
        learning["tested_idea_titles"] = tested_titles[-20:]
        self.write_json("learning_state.json", learning)
        self.write_text("lessons.md", self._render_lessons(runs, learning, learning["recent_runs"], result, improved_best))

        # Append to ledger
        self.append_ledger({
            "run_id": result.run_id,
            "timestamp": result.finished_at,
            "mode": result.plan.mode,
            "title": result.plan.title,
            "score": result.evaluation.score,
            "passed": result.evaluation.passed,
            "idea_source": result.plan.idea_source,
            "track": result.plan.track,
            "has_modified_script": bool(result.plan.modified_script),
        })
