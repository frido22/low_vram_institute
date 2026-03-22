from pathlib import Path
import json
import tempfile
import unittest

from lab.config import Paths
from lab.planner import Planner
from lab.state_store import StateStore


class PlannerTests(unittest.TestCase):
    def make_store(self) -> StateStore:
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        root = Path(temp_dir.name)
        (root / "state").mkdir()
        (root / "logs").mkdir()
        (root / "snapshots" / "research").mkdir(parents=True)
        (root / "config").mkdir()
        (root / "output" / "runs").mkdir(parents=True, exist_ok=True)
        (root / "output" / "reports").mkdir(parents=True, exist_ok=True)
        (root / "config" / "runtime.json").write_text(json.dumps({}))
        return StateStore(Paths.discover(root))

    def test_choose_explore_without_history(self) -> None:
        store = self.make_store()
        planner = Planner(store)
        self.assertEqual(planner.choose_mode(), "explore")

    def test_choose_exploit_after_first_success(self) -> None:
        store = self.make_store()
        # Add a ledger entry so best_score() returns something
        store.append_ledger({"run_id": "r1", "score": 2.29, "mode": "explore", "title": "baseline", "has_modified_script": False, "improved_best": True})
        planner = Planner(store)
        self.assertEqual(planner.choose_mode(), "exploit")


if __name__ == "__main__":
    unittest.main()
