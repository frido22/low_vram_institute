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

    def test_choose_exploit_after_first_success(self) -> None:
        store = self.make_store()
        store.write_json(
            "best_runs.json",
            {
                "best_score": 2.29,
                "higher_is_better": False,
                "runs": [{"run_id": "r1", "score": 2.29, "mode": "explore", "title": "baseline", "track": "mac_mini_official_like"}],
            },
        )
        store.write_json(
            "learning_state.json",
            {
                "plateau_count": 0,
                "recent_runs": [{"run_id": "r1", "score": 2.29, "mode": "explore", "title": "baseline", "improved_best": True, "needs_validation": False}],
                "best_score": 2.29,
                "last_improving_run_id": "r1",
                "tested_idea_titles": [],
            },
        )
        planner = Planner(store)
        self.assertEqual(planner.choose_mode(), "exploit")


if __name__ == "__main__":
    unittest.main()
