from pathlib import Path
import json
import tempfile
import unittest

from lab_core.config import Paths
from lab_core.services.github_intake import GitHubIntake
from lab_core.state_store import StateStore


class GitHubIntakeTests(unittest.TestCase):
    def make_env(self) -> tuple[Paths, StateStore, Path]:
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        root = Path(temp_dir.name)
        (root / "state").mkdir()
        (root / "logs").mkdir()
        (root / "snapshots" / "research").mkdir(parents=True)
        (root / "config").mkdir()
        (root.parent / "lab_public" / "runs").mkdir(parents=True, exist_ok=True)
        (root.parent / "lab_public" / "public").mkdir(parents=True, exist_ok=True)
        (root / "state" / "community_queue.jsonl").write_text("")
        issue_file = root / "snapshots" / "research" / "issues.json"
        issue_file.write_text(json.dumps([{"id": 1, "title": "Idea", "body": "Try it", "author": "alice", "url": "u"}]))
        (root / "config" / "sources.json").write_text(
            json.dumps({"github_sources": [{"id": "fixture", "kind": "file", "path": "snapshots/research/issues.json", "title": "fixture"}]})
        )
        (root / "config" / "runtime.json").write_text(json.dumps({}))
        return Paths.discover(root), StateStore(Paths.discover(root)), issue_file

    def test_refresh_imports_file_entries(self) -> None:
        paths, store, _ = self.make_env()
        intake = GitHubIntake(paths, store)
        rows = intake.refresh()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["title"], "Idea")


if __name__ == "__main__":
    unittest.main()
