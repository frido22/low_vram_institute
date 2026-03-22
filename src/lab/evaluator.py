from __future__ import annotations

import json
from typing import Any

from .models import Evaluation


class Evaluator:
    def evaluate(self, raw_result: dict) -> Evaluation:
        score = float(raw_result.get("score", 0.0))
        runtime = float(raw_result.get("runtime_seconds", 0.0))
        artifact_stats = raw_result.get("artifact_stats", {})
        passed = bool(raw_result.get("passed", True))
        higher_is_better = bool(raw_result.get("higher_is_better", True))

        # Analyze training curve from metrics
        curve_analysis = self._analyze_curve(raw_result.get("outputs", {}))
        artifact_stats["curve_analysis"] = curve_analysis

        needs_validation = raw_result.get("needs_validation", False)

        return Evaluation(
            score=score,
            runtime_seconds=runtime,
            passed=passed,
            artifact_stats=artifact_stats,
            needs_validation=needs_validation,
            higher_is_better=higher_is_better,
        )

    def _analyze_curve(self, outputs: dict[str, Any]) -> dict[str, Any]:
        """Parse metrics and produce training curve analysis."""
        metrics_text = outputs.get("metrics_jsonl", "")
        if not metrics_text:
            return {"status": "no_metrics"}

        steps: list[dict[str, float]] = []
        for line in metrics_text.strip().splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                steps.append(json.loads(line))
            except json.JSONDecodeError:
                continue

        if not steps:
            return {"status": "no_steps"}

        scores = [s.get("val_bpb", s.get("val_loss", 0.0)) for s in steps]
        n = len(scores)

        analysis: dict[str, Any] = {
            "total_steps": n,
            "first_score": scores[0] if scores else None,
            "last_score": scores[-1] if scores else None,
        }

        if n >= 2:
            improvement = scores[0] - scores[-1]
            analysis["total_improvement"] = round(improvement, 6)
            analysis["improving"] = improvement > 0.001

            mid = n // 2
            early_improvement = scores[0] - scores[mid] if mid > 0 else 0
            late_improvement = scores[mid] - scores[-1] if mid < n - 1 else 0
            analysis["early_improvement"] = round(early_improvement, 6)
            analysis["late_improvement"] = round(late_improvement, 6)

            if early_improvement > 0 and late_improvement > 0:
                analysis["curve_shape"] = "steady_descent"
            elif early_improvement > 0 and late_improvement <= 0.001:
                analysis["curve_shape"] = "early_plateau"
            elif early_improvement <= 0.001 and late_improvement > 0:
                analysis["curve_shape"] = "slow_start"
            else:
                analysis["curve_shape"] = "flat"

        return analysis
