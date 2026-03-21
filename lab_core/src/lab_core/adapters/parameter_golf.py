from __future__ import annotations

from datetime import datetime, timezone

from ..models import Plan


class ParameterGolfAdapter:
    def run(self, run_id: str, plan: Plan) -> dict:
        return {
            "score": 0.61,
            "runtime_seconds": 12.0,
            "artifact_stats": {
                "files_touched": 0,
                "log_lines": 2,
                "generated_at": datetime.now(timezone.utc).isoformat(),
            },
            "passed": True,
            "needs_validation": True,
            "patch": (
                "diff --git a/adapters/parameter_golf_placeholder.txt b/adapters/parameter_golf_placeholder.txt\n"
                "new file mode 100644\n"
                "--- /dev/null\n"
                "+++ b/adapters/parameter_golf_placeholder.txt\n"
                f"+run={run_id}\n"
                "+status=placeholder\n"
            ),
            "summary": (
                "Parameter Golf adapter placeholder executed. "
                "Apple Silicon local integration still needs the real benchmark harness."
            ),
            "logs": [
                "[adapter] parameter_golf placeholder start",
                "[adapter] awaiting real local harness wiring",
            ],
            "outputs": {"adapter": "parameter_golf", "experiment_name": "parameter_golf_placeholder"},
            "provenance": {"adapter": "parameter_golf", "placeholder": True, "plan_mode": plan.mode},
        }
