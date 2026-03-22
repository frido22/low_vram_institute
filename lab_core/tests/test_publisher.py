from pathlib import Path
import json
import tempfile
import unittest

from lab_core.config import Paths
from lab_core.models import Evaluation, Plan, RunResult
from lab_core.publisher import Publisher
from lab_core.state_store import StateStore


class PublisherTests(unittest.TestCase):
    def make_store(self) -> StateStore:
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        root = Path(temp_dir.name)
        (root / "state").mkdir()
        (root / "logs").mkdir()
        (root / "snapshots" / "research").mkdir(parents=True)
        (root / "config").mkdir()
        (root.parent / "lab_public" / "runs").mkdir(parents=True, exist_ok=True)
        (root.parent / "lab_public" / "public").mkdir(parents=True, exist_ok=True)
        (root / "config" / "runtime.json").write_text(json.dumps({}))
        (root / "state" / "best_runs.json").write_text(json.dumps({"best_score": 0.8, "runs": [{"run_id": "r", "score": 0.8, "mode": "explore"}]}))
        (root / "state" / "agenda.md").write_text("# Agenda\n")
        return StateStore(Paths.discover(root))

    def test_publish_writes_summary(self) -> None:
        store = self.make_store()
        publisher = Publisher(store)
        result = RunResult(
            run_id="run_1",
            started_at="2026-01-01T00:00:00+00:00",
            finished_at="2026-01-01T00:00:01+00:00",
            plan=Plan(
                mode="explore",
                title="test",
                rationale="why",
                expected_signal="signal",
                public_updates=["current_status"],
                adapter="parameter_golf",
                logging_focus=["baseline score"],
            ),
            evaluation=Evaluation(score=0.7, runtime_seconds=1.0, passed=True, artifact_stats={}, needs_validation=False),
            patch="diff --git a/x b/x",
            summary="summary",
        )
        publisher.publish(result)
        summary_path = store.paths.public_runs_dir / "run_1" / "summary.md"
        self.assertTrue(summary_path.exists())


if __name__ == "__main__":
    unittest.main()
