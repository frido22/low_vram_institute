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
        for path in [paths.state_dir, paths.logs_dir, paths.public_root,
                     paths.public_runs_dir, paths.public_pages_dir]:
            path.mkdir(parents=True, exist_ok=True)

    # --- Readers ---

    def _read_json(self, path: Path, default: Any) -> Any:
        return json.loads(path.read_text()) if path.exists() else default

    def _read_text(self, path: Path, default: str) -> str:
        return path.read_text() if path.exists() else default

    def best_score(self) -> float | None:
        rows = self.ledger_rows()
        if not rows:
            return None
        return min(r["score"] for r in rows)

    def best_script(self) -> str | None:
        data = self._read_json(self.paths.state_dir / "best_script.json", None)
        if isinstance(data, dict):
            return data.get("modified_script")
        return None

    def best_diff(self) -> str:
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

    # --- Curve analysis ---

    def _analyze_curve(self, outputs: dict[str, Any]) -> str:
        """One-word training curve shape from metrics_jsonl. Zero overhead."""
        text = outputs.get("metrics_jsonl", "")
        if not text:
            return "no_data"
        scores = []
        for line in text.strip().splitlines():
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
        if early > 0.001 and late <= 0.001:
            return "plateaued"
        if early <= 0.001 and late > 0.001:
            return "slow_start"
        return "flat"

    # --- Prompt context ---

    def render_context(self) -> str:
        """Render full history into dense prompt context. Scales to 1000 runs."""
        rows = self.ledger_rows()
        if not rows:
            return "No runs yet."

        best = min(rows, key=lambda r: r["score"])
        improvements = [r for r in rows if r.get("improved_best")]
        plateau = len(rows) - max((i for i, r in enumerate(rows) if r.get("improved_best")), default=0) - 1

        lines: list[str] = []

        # Scoreboard
        lines.append(f"Best: {best['score']:.4f} ({best['run_id']}) | {best.get('title', '')}")
        lines.append(f"Runs: {len(rows)} | Improvements: {len(improvements)} | Plateau streak: {plateau}")
        lines.append("")

        # Recent runs with diagnostics
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

        # Failed modifications — unique titles only, most recent last
        failed = [r for r in rows if not r.get("improved_best") and r.get("has_modified_script")]
        if failed:
            seen: set[str] = set()
            unique_fails: list[str] = []
            for r in reversed(failed):
                title = r.get("title", "")
                if title not in seen:
                    seen.add(title)
                    unique_fails.append(f"- {title} ({r['score']:.4f})")
            lines.append(f"Failed modifications ({len(failed)} total, don't repeat):")
            lines.extend(unique_fails[:20])
            lines.append("")

        # Compound path — every improvement
        if improvements:
            lines.append("Improvements (the path to current best):")
            for r in improvements:
                mod = "+script" if r.get("has_modified_script") else "baseline"
                lines.append(f"- {r['run_id']} {r['score']:.4f} [{mod}] {r.get('title', '')}")
            lines.append("")

        return "\n".join(lines)

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

    # --- Update after run ---

    def save_best_script(self, result: RunResult) -> None:
        if not result.plan.modified_script:
            return
        self.write_json("best_script.json", {
            "run_id": result.run_id,
            "score": result.evaluation.score,
            "title": result.plan.title,
            "modified_script": result.plan.modified_script,
        })
        self.write_text("best_diff.patch", result.patch)

    def update_after_run(self, result: RunResult) -> None:
        rows = self.ledger_rows()
        prior_best = min((r["score"] for r in rows), default=None)
        improved = prior_best is None or result.evaluation.score < prior_best

        if improved and result.plan.modified_script:
            self.save_best_script(result)

        # Extract diagnostics from adapter output
        diag = (result.outputs or {}).get("diagnostics", {})

        # Curve analysis from metrics_jsonl
        curve = self._analyze_curve(result.outputs or {})

        self.append_ledger({
            "run_id": result.run_id,
            "timestamp": result.finished_at,
            "mode": result.plan.mode,
            "title": result.plan.title,
            "score": result.evaluation.score,
            "passed": result.evaluation.passed,
            "has_modified_script": bool(result.plan.modified_script),
            "improved_best": improved,
            "runtime_seconds": result.evaluation.runtime_seconds,
            "step_count": diag.get("step_count", 0),
            "avg_tok_s": diag.get("avg_tok_s"),
            "peak_mb": diag.get("peak_mb"),
            "active_mb": diag.get("active_mb"),
            "quantized_bytes": diag.get("quantized_bytes"),
            "curve": curve,
            "track": result.plan.track,
        })

        self.write_json("current_state.json", {
            "last_run_id": result.run_id,
            "last_score": result.evaluation.score,
            "last_status": "passed" if result.evaluation.passed else "failed",
            "last_title": result.plan.title,
            "updated_at": result.finished_at,
        })
