from __future__ import annotations

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

    def build_env(self, run_id: str, out_dir: Optional[Path] = None) -> dict[str, str]:
        env = os.environ.copy()
        env["RUN_ID"] = run_id
        env["OUT_DIR"] = str(out_dir or (self.paths.logs_dir / "parameter_golf"))
        env.setdefault("DATA_PATH", str(self.workspace / "data" / "datasets" / f"fineweb10B_{self.runtime.get('dataset_variant', 'sp1024')}"))
        env.setdefault("TOKENIZER_PATH", str(self.workspace / "data" / "tokenizers" / "fineweb_1024_bpe.model"))
        # Reproducible Mac mini launch baseline. The planner can still rewrite the
        # script freely, but runs should start from settings that are known to fit
        # this machine instead of silently falling back to large upstream defaults.
        env.setdefault("ITERATIONS", str(self.runtime.get("iterations", 200)))
        env.setdefault("TRAIN_BATCH_TOKENS", str(self.runtime.get("train_batch_tokens", 8192)))
        env.setdefault("VAL_BATCH_SIZE", str(self.runtime.get("val_batch_size", 8192)))
        env.setdefault("VAL_LOSS_EVERY", str(self.runtime.get("val_loss_every", 0)))
        env.setdefault("TRAIN_LOG_EVERY", str(self.runtime.get("train_log_every", 25)))
        env.setdefault("MAX_WALLCLOCK_SECONDS", str(self.runtime.get("max_wallclock_seconds", 600)))
        env.setdefault("MLX_EAGER_EVAL", str(int(bool(self.runtime.get("mlx_eager_eval", True)))))
        env.setdefault("MLX_MAX_MICROBATCH_TOKENS", str(self.runtime.get("mlx_max_microbatch_tokens", 8192)))
        return env
