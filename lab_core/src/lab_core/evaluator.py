from __future__ import annotations

from .models import Evaluation


class Evaluator:
    def evaluate(self, raw_result: dict) -> Evaluation:
        score = float(raw_result.get("score", 0.0))
        runtime = float(raw_result.get("runtime_seconds", 0.0))
        artifact_stats = raw_result.get("artifact_stats", {})
        passed = bool(raw_result.get("passed", True))
        needs_validation = raw_result.get("needs_validation", score > 0.8)
        return Evaluation(
            score=score,
            runtime_seconds=runtime,
            passed=passed,
            artifact_stats=artifact_stats,
            needs_validation=needs_validation,
        )
