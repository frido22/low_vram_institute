from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import json
from typing import Any, Optional


@dataclass(frozen=True)
class Paths:
    root: Path
    state_dir: Path
    logs_dir: Path
    snapshots_dir: Path
    research_dir: Path
    public_root: Path
    public_runs_dir: Path
    public_pages_dir: Path
    config_dir: Path

    @classmethod
    def discover(cls, root: Optional[Path] = None) -> "Paths":
        base = (root or Path(__file__).resolve().parents[2]).resolve()
        public_root = (base.parent / "lab_public").resolve()
        return cls(
            root=base,
            state_dir=base / "state",
            logs_dir=base / "logs",
            snapshots_dir=base / "snapshots",
            research_dir=base / "snapshots" / "research",
            public_root=public_root,
            public_runs_dir=public_root / "runs",
            public_pages_dir=public_root / "public",
            config_dir=base / "config",
        )


@dataclass(frozen=True)
class LabConfig:
    min_free_disk_bytes: int = 2_000_000_000
    heartbeat_seconds: int = 10
    stale_lock_seconds: int = 3600
    base_backoff_seconds: int = 10
    max_backoff_seconds: int = 300
    max_cycles: Optional[int] = None


def load_json_config(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text()) if path.exists() else {}


def load_sources(paths: Paths) -> dict:
    config_path = paths.config_dir / "sources.json"
    return load_json_config(config_path)


def load_runtime(paths: Paths) -> dict[str, Any]:
    return load_json_config(paths.config_dir / "runtime.json")
