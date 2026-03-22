from pathlib import Path
import json
import tempfile
import unittest

from lab.config import LabConfig, Paths
from lab.supervisor import Supervisor


class StubParameterGolfAdapter:
    def run(self, run_id, plan):
        return {
            "score": 1.0,
            "runtime_seconds": 1.0,
            "artifact_stats": {},
            "passed": True,
            "needs_validation": False,
            "higher_is_better": False,
            "patch": "",
            "summary": "stub run",
            "outputs": {},
            "provenance": {},
        }


class SupervisorTests(unittest.TestCase):
    def make_root(self) -> Path:
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        root = Path(temp_dir.name)
        (root / "state").mkdir()
        (root / "logs").mkdir()
        (root / "snapshots" / "research").mkdir(parents=True)
        (root / "config").mkdir()
        (root / "output" / "runs").mkdir(parents=True, exist_ok=True)
        (root / "output" / "reports").mkdir(parents=True, exist_ok=True)
        (root / "config" / "runtime.json").write_text(json.dumps({"codex": {"enabled": False}}))
        (root / "config" / "sources.json").write_text(json.dumps({"github_sources": [], "research_sources": []}))
        return root

    def test_run_once_returns_run_id(self) -> None:
        root = self.make_root()
        supervisor = Supervisor(Paths.discover(root), LabConfig(min_free_disk_bytes=1, max_cycles=1))
        supervisor.executor.adapters["parameter_golf"] = StubParameterGolfAdapter()
        run_id = supervisor.run_once()
        self.assertIn("_run_", run_id)


if __name__ == "__main__":
    unittest.main()
