from pathlib import Path
import json
import tempfile
import unittest

from lab_core.config import LabConfig, Paths
from lab_core.supervisor import Supervisor


class SupervisorTests(unittest.TestCase):
    def make_root(self) -> Path:
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
        (root / "config" / "sources.json").write_text(json.dumps({"github_sources": [], "research_sources": []}))
        (root / "state" / "current_state.json").write_text(json.dumps({"last_status": "idle"}))
        (root / "state" / "best_runs.json").write_text(json.dumps({"best_score": None, "runs": []}))
        (root / "state" / "community_queue.jsonl").write_text("")
        (root / "state" / "agenda.md").write_text("# Agenda\n")
        (root / "state" / "insights.md").write_text("# Insights\n")
        return root

    def test_run_once_returns_run_id(self) -> None:
        root = self.make_root()
        supervisor = Supervisor(Paths.discover(root), LabConfig(min_free_disk_bytes=1, max_cycles=1))
        run_id = supervisor.run_once()
        self.assertIn("_run_", run_id)


if __name__ == "__main__":
    unittest.main()
