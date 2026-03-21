from __future__ import annotations

import json
from typing import Any

from ..config import Paths, load_runtime, load_sources
from ..state_store import StateStore
from .github_client import GitHubClient


class GitHubIntake:
    def __init__(self, paths: Paths, store: StateStore) -> None:
        self.paths = paths
        self.store = store
        self.runtime = load_runtime(paths)
        self.client = GitHubClient()

    def _load_file_source(self, source: dict[str, Any]) -> list[dict[str, Any]]:
        path = (self.paths.root / source["path"]).resolve()
        if not path.exists():
            return []
        payload = json.loads(path.read_text())
        entries = payload if isinstance(payload, list) else payload.get("items", [])
        normalized = []
        for entry in entries:
            normalized.append(
                {
                    "id": f"github:{entry['id']}",
                    "title": entry["title"],
                    "body": entry.get("body", ""),
                    "author": entry.get("author", "unknown"),
                    "url": entry.get("url", ""),
                    "status": "queued",
                    "source": source["id"],
                }
            )
        return normalized

    def refresh(self) -> list[dict[str, Any]]:
        sources = load_sources(self.paths).get("github_sources", [])
        rows: list[dict[str, Any]] = []
        for source in sources:
            if source.get("kind") == "file":
                rows.extend(self._load_file_source(source))
            if source.get("kind") == "github_issues":
                rows.extend(self._load_live_issues(source))
        queue_path = self.paths.state_dir / "community_queue.jsonl"
        seen = {row["id"] for row in self.store.community_queue()}
        with queue_path.open("a") as handle:
            for row in rows:
                if row["id"] in seen:
                    continue
                handle.write(json.dumps(row, sort_keys=True) + "\n")
                seen.add(row["id"])
        return self.store.community_queue()

    def _load_live_issues(self, source: dict[str, Any]) -> list[dict[str, Any]]:
        github = self.runtime.get("github", {})
        owner = github.get("owner")
        repo = github.get("repo")
        if not owner or not repo or not github.get("issues_enabled", True) or not self.client.configured():
            return []
        items = self.client.list_issues(owner, repo)
        return [
            {
                "id": f"github:{item['id']}",
                "title": item["title"],
                "body": item.get("body") or "",
                "author": (item.get("user") or {}).get("login", "unknown"),
                "url": item.get("html_url", ""),
                "status": "queued",
                "source": source["id"],
            }
            for item in items
        ]
