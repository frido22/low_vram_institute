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

    def _scan_upstream_records(self) -> list[dict[str, Any]]:
        """Scan local Parameter Golf records for research context."""
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
                    name = readme.parent.name
                    notes.append({
                        "id": f"upstream_{track_dir.name}_{name}",
                        "title": f"Upstream record: {name}",
                        "captured_at": datetime.now(timezone.utc).isoformat(),
                        "body": text[:3000],
                        "source": "upstream_records",
                    })
                except OSError:
                    continue
        return notes

    def refresh(self) -> list[dict[str, Any]]:
        notes = []

        # Configured research sources
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

        # Upstream Parameter Golf records (local, always fresh)
        upstream = self._scan_upstream_records()
        notes.extend(upstream)

        return notes
