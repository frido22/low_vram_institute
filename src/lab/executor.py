from __future__ import annotations

from datetime import datetime, timezone

from .adapters.parameter_golf import ParameterGolfAdapter
from .evaluator import Evaluator
from .models import Plan, RunResult
from .state_store import StateStore


class Executor:
    def __init__(self, store: StateStore) -> None:
        self.store = store
        self.evaluator = Evaluator()
        self.adapters = {
            "parameter_golf": ParameterGolfAdapter(store.paths),
        }

    def execute(self, run_id: str, plan: Plan) -> RunResult:
        started_at = datetime.now(timezone.utc).isoformat()
        self.store.snapshot_state(run_id)
        self.store.write_checkpoint("executing", run_id, {"adapter": plan.adapter})
        raw = self.adapters[plan.adapter].run(run_id, plan)
        evaluation = self.evaluator.evaluate(raw)
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
