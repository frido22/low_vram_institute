from __future__ import annotations

from datetime import datetime, timezone
import json
from typing import Any
from urllib.request import urlopen

from ..config import Paths, load_sources


class ResearchSnapshotService:
    def __init__(self, paths: Paths) -> None:
        self.paths = paths

    def _fetch_text(self, source: dict[str, Any]) -> str:
        if source.get("kind") == "file":
            path = (self.paths.root / source["path"]).resolve()
            return path.read_text() if path.exists() else ""
        if source.get("kind") == "url":
            with urlopen(source["url"], timeout=15) as response:  # noqa: S310
                return response.read().decode("utf-8", errors="replace")
        return ""

    def refresh(self) -> list[dict[str, Any]]:
        notes = []
        for source in load_sources(self.paths).get("research_sources", []):
            text = self._fetch_text(source).strip()
            snapshot = {
                "id": source["id"],
                "title": source["title"],
                "captured_at": datetime.now(timezone.utc).isoformat(),
                "body": text[:12000],
            }
            path = self.paths.research_dir / f"{source['id']}.json"
            path.write_text(json.dumps(snapshot, indent=2, sort_keys=True) + "\n")
            notes.append(snapshot)
        return notes
