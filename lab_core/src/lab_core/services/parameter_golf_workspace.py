from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Any, Optional

from ..config import Paths, load_runtime


class ParameterGolfWorkspace:
    def __init__(self, paths: Paths) -> None:
        self.paths = paths
        self.runtime = load_runtime(paths).get("parameter_golf", {})
        self.workspace = Path(self.runtime.get("workspace", paths.root / "third_party" / "parameter-golf")).resolve()
        self.python = self.runtime.get("venv_python", str(self.workspace / ".venv_pg" / "bin" / "python3"))

    def bootstrap(self) -> dict[str, Any]:
        status = {
            "workspace_exists": self.workspace.exists(),
            "python_exists": Path(self.python).exists(),
            "dataset_ready": self.dataset_ready(),
            "workspace": str(self.workspace),
            "python": self.python,
        }
        return status

    def dataset_ready(self) -> bool:
        variant = self.runtime.get("dataset_variant", "sp1024")
        dataset_dir = self.workspace / "data" / "datasets" / f"fineweb10B_{variant}"
        tokenizer = self.workspace / "data" / "tokenizers" / "fineweb_1024_bpe.model"
        return dataset_dir.exists() and tokenizer.exists() and bool(list(dataset_dir.glob("fineweb_val_*.bin")))

    def prepare_proxy_dataset(self) -> Path:
        variant = self.runtime.get("dataset_variant", "sp1024")
        source = self.workspace / "data" / "datasets" / f"fineweb10B_{variant}"
        target = self.workspace / "data" / "datasets" / f"fineweb10B_{variant}_macmini_proxy"
        target.mkdir(parents=True, exist_ok=True)
        self._copy_trimmed_subset(
            source,
            target,
            "fineweb_train_*.bin",
            int(self.runtime.get("proxy_train_shards", 1)),
            int(self.runtime.get("proxy_train_tokens", 1_048_576)),
        )
        self._copy_trimmed_subset(
            source,
            target,
            "fineweb_val_*.bin",
            int(self.runtime.get("proxy_val_shards", 1)),
            int(self.runtime.get("proxy_val_tokens", 262_144)),
        )
        return target

    def _copy_trimmed_subset(self, source: Path, target: Path, pattern: str, limit: int, token_limit: int) -> None:
        files = sorted(source.glob(pattern))[:limit]
        if not files:
            raise FileNotFoundError(f"No files found for proxy dataset pattern {pattern} in {source}")
        for path in files:
            dest = target / path.name
            if dest.exists() and self._shard_token_count(dest) == min(self._shard_token_count(path), token_limit):
                continue
            self._write_trimmed_shard(path, dest, token_limit)

    def _write_trimmed_shard(self, source: Path, dest: Path, token_limit: int) -> None:
        header_bytes = 256 * 4
        raw = source.read_bytes()
        header = bytearray(raw[:header_bytes])
        total_tokens = int.from_bytes(header[8:12], "little", signed=True)
        keep_tokens = min(total_tokens, token_limit)
        header[8:12] = int(keep_tokens).to_bytes(4, "little", signed=True)
        payload = raw[header_bytes : header_bytes + keep_tokens * 2]
        dest.write_bytes(bytes(header) + payload)

    def _shard_token_count(self, path: Path) -> int:
        header = path.read_bytes()[: 256 * 4]
        return int.from_bytes(header[8:12], "little", signed=True)

    def download_dataset(self) -> subprocess.CompletedProcess:
        train_shards = str(self.runtime.get("train_shards", 1))
        command = [
            self.python,
            "data/cached_challenge_fineweb.py",
            "--variant",
            self.runtime.get("dataset_variant", "sp1024"),
            "--train-shards",
            train_shards,
        ]
        return subprocess.run(  # noqa: S603
            command,
            cwd=self.workspace,
            capture_output=True,
            text=True,
            check=False,
        )

    def build_env(self, run_id: str, overrides: Optional[dict[str, str]] = None, out_dir: Optional[Path] = None) -> dict[str, str]:
        env = os.environ.copy()
        env.update({str(k): str(v) for k, v in self.runtime.get("default_env", {}).items()})
        if overrides:
            env.update({str(k): str(v) for k, v in overrides.items()})
        env["RUN_ID"] = run_id
        env["OUT_DIR"] = str(out_dir or (self.paths.logs_dir / "parameter_golf"))
        env.setdefault("DATA_PATH", str(self.prepare_proxy_dataset()))
        env.setdefault("TOKENIZER_PATH", str(self.workspace / "data" / "tokenizers" / "fineweb_1024_bpe.model"))
        return env
