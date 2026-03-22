from __future__ import annotations

from datetime import datetime, timezone

from .adapters.parameter_golf import ParameterGolfAdapter
from .models import Evaluation, Plan, RunResult
from .state_store import StateStore


class Executor:
    def __init__(self, store: StateStore) -> None:
        self.store = store
        self.adapters = {
            "parameter_golf": ParameterGolfAdapter(store.paths),
        }

    def execute(self, run_id: str, plan: Plan) -> RunResult:
        started_at = datetime.now(timezone.utc).isoformat()
        self.store.write_checkpoint("executing", run_id, {"adapter": plan.adapter})
        raw = self.adapters[plan.adapter].run(run_id, plan)

        evaluation = Evaluation(
            score=float(raw.get("score", 0.0)),
            runtime_seconds=float(raw.get("runtime_seconds", 0.0)),
            passed=bool(raw.get("passed", True)),
            artifact_stats=raw.get("artifact_stats", {}),
            needs_validation=raw.get("needs_validation", False),
            higher_is_better=bool(raw.get("higher_is_better", True)),
        )

        finished_at = datetime.now(timezone.utc).isoformat()
        summary = (
            f"{raw['summary']} Score={evaluation.score:.4f}. "
            f"Expected signal: {plan.expected_signal}"
        )
        return RunResult(
            run_id=run_id,
            started_at=started_at,
            finished_at=finished_at,
            plan=plan,
            evaluation=evaluation,
            patch=raw["patch"],
            summary=summary,
            outputs=raw.get("outputs", {}),
            provenance=raw.get("provenance", {}),
        )
