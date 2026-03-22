from pathlib import Path
import json
import tempfile
import unittest

from lab.config import Paths
from lab.services.parameter_golf_workspace import ParameterGolfWorkspace


class ParameterGolfWorkspaceTests(unittest.TestCase):
    def test_build_env_uses_mac_mini_baseline(self) -> None:
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        root = Path(temp_dir.name)
        (root / "state").mkdir()
        (root / "logs").mkdir()
        (root / "snapshots" / "research").mkdir(parents=True)
        (root / "config").mkdir()
        (root / "output" / "runs").mkdir(parents=True, exist_ok=True)
        (root / "output" / "reports").mkdir(parents=True, exist_ok=True)
        runtime = {
            "parameter_golf": {
                "workspace": str(root / "third_party" / "parameter-golf"),
                "dataset_variant": "sp1024",
                "iterations": 200,
                "train_batch_tokens": 8192,
                "val_batch_size": 8192,
                "val_loss_every": 0,
                "train_log_every": 25,
                "max_wallclock_seconds": 600,
                "mlx_eager_eval": True,
                "mlx_max_microbatch_tokens": 8192,
            }
        }
        (root / "config" / "runtime.json").write_text(json.dumps(runtime))
        workspace = root / "third_party" / "parameter-golf" / "data" / "tokenizers"
        workspace.mkdir(parents=True, exist_ok=True)
        pg = ParameterGolfWorkspace(Paths.discover(root))
        env = pg.build_env("run_1")
        self.assertEqual(env["ITERATIONS"], "200")
        self.assertEqual(env["TRAIN_BATCH_TOKENS"], "8192")
        self.assertEqual(env["VAL_BATCH_SIZE"], "8192")
        self.assertEqual(env["MAX_WALLCLOCK_SECONDS"], "600")
        self.assertEqual(env["MLX_EAGER_EVAL"], "1")


if __name__ == "__main__":
    unittest.main()
