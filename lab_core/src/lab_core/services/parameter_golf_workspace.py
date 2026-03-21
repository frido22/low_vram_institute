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
        env.setdefault("DATA_PATH", str(self.workspace / "data" / "datasets" / f"fineweb10B_{self.runtime.get('dataset_variant', 'sp1024')}"))
        env.setdefault("TOKENIZER_PATH", str(self.workspace / "data" / "tokenizers" / "fineweb_1024_bpe.model"))
        return env
