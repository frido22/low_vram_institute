from pathlib import Path
import json
import tempfile
import unittest

from lab.config import Paths
from lab.models import Evaluation, Plan, RunResult
from lab.publisher import Publisher
from lab.state_store import StateStore


class PublisherTests(unittest.TestCase):
    def make_store(self) -> StateStore:
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        root = Path(temp_dir.name)
        (root / "state").mkdir()
        (root / "logs").mkdir()
        (root / "snapshots" / "research").mkdir(parents=True)
        (root / "config").mkdir()
        (root / "output" / "runs").mkdir(parents=True, exist_ok=True)
        (root / "output" / "public").mkdir(parents=True, exist_ok=True)
        (root / "config" / "runtime.json").write_text(json.dumps({}))
        (root / "state" / "best_runs.json").write_text(json.dumps({"best_score": 0.8, "runs": [{"run_id": "r", "score": 0.8, "mode": "explore"}]}))
        return StateStore(Paths.discover(root))

    def test_publish_writes_artifacts(self) -> None:
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
                idea_id=None,
            ),
            evaluation=Evaluation(score=0.7, runtime_seconds=1.0, passed=True, artifact_stats={}, needs_validation=False),
            patch="",
            summary="summary",
        )
        publisher.publish(result)
        run_dir = store.paths.public_runs_dir / "run_1"
        self.assertTrue((run_dir / "submission.json").exists())
        self.assertTrue((run_dir / "README.md").exists())
        self.assertTrue((run_dir / "metrics.json").exists())
        self.assertTrue((run_dir / "diff.patch").exists())
        sub = json.loads((run_dir / "submission.json").read_text())
        self.assertAlmostEqual(sub["val_bpb"], 0.7)
        self.assertEqual(sub["title"], "test")

    def test_publish_with_modified_script(self) -> None:
        store = self.make_store()
        publisher = Publisher(store)
        result = RunResult(
            run_id="run_2",
            started_at="2026-01-01T00:00:00+00:00",
            finished_at="2026-01-01T00:00:01+00:00",
            plan=Plan(
                mode="exploit",
                title="test modified",
                rationale="testing full script",
                expected_signal="signal",
                public_updates=["overview"],
                adapter="parameter_golf",
                modified_script="# modified training script\nprint('hello')\n",
            ),
            evaluation=Evaluation(score=0.5, runtime_seconds=2.0, passed=True, artifact_stats={}, needs_validation=False),
            patch="--- a/train_gpt_mlx.py\n+++ b/train_gpt_mlx.py\n@@ -1 +1,2 @@\n+# modified\n",
            summary="improved",
            outputs={"train_script": "# modified training script\nprint('hello')\n"},
        )
        publisher.publish(result)
        run_dir = store.paths.public_runs_dir / "run_2"
        self.assertTrue((run_dir / "train_gpt.py").exists())
        self.assertIn("modified", (run_dir / "train_gpt.py").read_text())
        readme = (run_dir / "README.md").read_text()
        self.assertIn("```diff", readme)


if __name__ == "__main__":
    unittest.main()
