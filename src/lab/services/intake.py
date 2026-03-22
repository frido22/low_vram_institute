from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from typing import Any
from urllib.request import Request, urlopen

from ..config import Paths, load_sources


class IntakeService:
    """Unified intake: community ideas (GitHub) + research snapshots."""

    def __init__(self, paths: Paths) -> None:
        self.paths = paths

    def refresh(self) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        """Return (community_ideas, research_notes)."""
        sources = load_sources(self.paths)
        community = self._refresh_community(sources.get("github_sources", []))
        research = self._refresh_research(sources.get("research_sources", []))
        return community, research

    # --- Community (GitHub issues + file sources) ---

    def _refresh_community(self, sources: list[dict]) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for source in sources:
            if source.get("kind") == "file":
                rows.extend(self._load_file_source(source))
            elif source.get("kind") == "github_issues":
                rows.extend(self._load_github_issues(source))
        return rows

    def _load_file_source(self, source: dict[str, Any]) -> list[dict[str, Any]]:
        path = (self.paths.root / source["path"]).resolve()
        if not path.exists():
            return []
        payload = json.loads(path.read_text())
        entries = payload if isinstance(payload, list) else payload.get("items", [])
        return [
            {
                "id": f"github:{entry['id']}",
                "title": entry["title"],
                "body": entry.get("body", "")[:500],
                "author": entry.get("author", "unknown"),
            }
            for entry in entries
        ]

    def _load_github_issues(self, source: dict[str, Any]) -> list[dict[str, Any]]:
        token = os.environ.get("GITHUB_TOKEN")
        if not token:
            return []
        owner = source.get("owner", "")
        repo = source.get("repo", "")
        if not owner or not repo:
            return []
        url = f"https://api.github.com/repos/{owner}/{repo}/issues?state=open&per_page=10"
        headers = {
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "User-Agent": "low-vram-institute",
        }
        try:
            request = Request(url, headers=headers)
            with urlopen(request, timeout=15) as response:  # noqa: S310
                items = json.loads(response.read().decode("utf-8"))
        except Exception:
            return []
        return [
            {
                "id": f"github:{item['id']}",
                "title": item["title"],
                "body": (item.get("body") or "")[:500],
                "author": (item.get("user") or {}).get("login", "unknown"),
            }
            for item in items
            if "pull_request" not in item
        ]

    # --- Research snapshots ---

    def _refresh_research(self, sources: list[dict]) -> list[dict[str, Any]]:
        notes: list[dict[str, Any]] = []
        for source in sources:
            text = self._fetch_text(source).strip()
            if text:
                notes.append({"title": source.get("title", source["id"]), "body": text[:3000]})
        # Upstream Parameter Golf records (local)
        notes.extend(self._scan_upstream_records())
        return notes

    def _fetch_text(self, source: dict[str, Any]) -> str:
        if source.get("kind") == "file":
            path = (self.paths.root / source["path"]).resolve()
            return path.read_text() if path.exists() else ""
        if source.get("kind") == "url":
            try:
                with urlopen(source["url"], timeout=15) as response:  # noqa: S310
                    return response.read().decode("utf-8", errors="replace")
            except Exception:
                return ""
        return ""

    def _scan_upstream_records(self) -> list[dict[str, Any]]:
        records_root = self.paths.root / "third_party" / "parameter-golf" / "records"
        if not records_root.exists():
            return []
        notes: list[dict[str, Any]] = []
        for track_dir in sorted(records_root.iterdir()):
            if not track_dir.is_dir():
                continue
            for readme in sorted(track_dir.glob("*/README.md")):
                try:
                    text = readme.read_text()
                    notes.append({"title": f"Upstream: {readme.parent.name}", "body": text[:2000]})
                except OSError:
                    continue
        return notes[:10]
