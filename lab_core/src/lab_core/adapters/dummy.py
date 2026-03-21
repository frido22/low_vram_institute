from __future__ import annotations

from datetime import datetime, timezone
from random import Random

from ..models import Plan


class DummyAdapter:
    def run(self, run_id: str, plan: Plan) -> dict:
        seed = sum(ord(ch) for ch in run_id + plan.mode)
        rng = Random(seed)
        score = 0.45 + rng.random() * 0.4
        return {
            "score": round(score, 4),
            "runtime_seconds": round(3 + rng.random() * 5, 2),
            "artifact_stats": {
                "files_touched": 1,
                "log_lines": 5,
                "generated_at": datetime.now(timezone.utc).isoformat(),
            },
            "passed": True,
            "needs_validation": score > 0.75,
            "patch": (
                "diff --git a/experiments/dummy.txt b/experiments/dummy.txt\n"
                "new file mode 100644\n"
                "--- /dev/null\n"
                "+++ b/experiments/dummy.txt\n"
                f"+run={run_id}\n"
                f"+mode={plan.mode}\n"
            ),
            "summary": f"{plan.mode.title()} run completed against the dummy adapter.",
            "logs": [
                f"[adapter] starting {plan.mode}",
                f"[adapter] title={plan.title}",
                f"[adapter] score={score:.4f}",
            ],
            "outputs": {"adapter": "dummy", "experiment_name": "dummy_baseline"},
            "provenance": {"adapter": "dummy", "seed": seed},
        }
