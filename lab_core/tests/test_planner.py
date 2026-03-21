from pathlib import Path
import json
import tempfile
import unittest

from lab_core.config import Paths
from lab_core.planner import Planner
from lab_core.state_store import StateStore


class PlannerTests(unittest.TestCase):
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
        (root / "state" / "current_state.json").write_text(json.dumps({"last_status": "idle"}))
        (root / "state" / "best_runs.json").write_text(json.dumps({"best_score": None, "runs": []}))
        (root / "state" / "community_queue.jsonl").write_text("")
        return StateStore(Paths.discover(root))

    def test_choose_explore_without_history(self) -> None:
        store = self.make_store()
        planner = Planner(store)
        self.assertEqual(planner.choose_mode(), "explore")


if __name__ == "__main__":
    unittest.main()
