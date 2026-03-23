"""Parameter Golf adapter — runs train_gpt_mlx.py, captures metrics."""
from __future__ import annotations

from datetime import datetime, timezone
import difflib
import os
import re
import subprocess
from pathlib import Path


FINAL_EXACT_RE = re.compile(r"final_int8_zlib_roundtrip_exact val_loss:(?P<val_loss>[0-9.]+) val_bpb:(?P<val_bpb>[0-9.]+)")
REQUIRED_MARKERS = ["final_int8_zlib_roundtrip_exact", "MAX_WALLCLOCK_SECONDS"]
MAX_SCRIPT_LINES = 1500


def _emit(message: str) -> None:
    print(f"[parameter_golf] {message}", flush=True)


#Workspace helpers (merged from parameter_golf_workspace.py)

class Workspace:
    def __init__(self, pg_config: dict, logs_dir: Path) -> None:
        self.config = pg_config
        self.logs_dir = logs_dir
        self.path = Path(pg_config.get("workspace", "")).resolve()
        self.python = pg_config.get("venv_python", str(self.path / ".venv_pg" / "bin" / "python3"))

    def bootstrap(self) -> dict:
        return {
            "workspace_exists": self.path.exists(),
            "python_exists": Path(self.python).exists(),
            "dataset_ready": self._dataset_ready(),
        }

    def _dataset_ready(self) -> bool:
        variant = self.config.get("dataset_variant", "sp1024")
        ds = self.path / "data" / "datasets" / f"fineweb10B_{variant}"
        tok = self.path / "data" / "tokenizers" / "fineweb_1024_bpe.model"
        return ds.exists() and tok.exists() and bool(list(ds.glob("fineweb_val_*.bin")))

    def download_dataset(self) -> subprocess.CompletedProcess:
        return subprocess.run(  # noqa: S603
            [self.python, "data/cached_challenge_fineweb.py",
             "--variant", self.config.get("dataset_variant", "sp1024"),
             "--train-shards", str(self.config.get("train_shards", 1))],
            cwd=self.path, capture_output=True, text=True, check=False,
        )

    def build_env(self, run_id: str) -> dict[str, str]:
        env = os.environ.copy()
        env["RUN_ID"] = run_id
        env["OUT_DIR"] = str(self.logs_dir / "parameter_golf")
        variant = self.config.get("dataset_variant", "sp1024")
        env.setdefault("DATA_PATH", str(self.path / "data" / "datasets" / f"fineweb10B_{variant}"))
        env.setdefault("TOKENIZER_PATH", str(self.path / "data" / "tokenizers" / "fineweb_1024_bpe.model"))
        env.setdefault("MAX_WALLCLOCK_SECONDS", str(self.config.get("max_wallclock_seconds", 600)))
        env.setdefault("MLX_EAGER_EVAL", str(int(bool(self.config.get("mlx_eager_eval", True)))))
        return env


#Adapter

def run(run_id: str, plan: dict, pg_config: dict, logs_dir: Path) -> dict:
    """Run one Parameter Golf training cycle. Returns flat result dict."""
    ws = Workspace(pg_config, logs_dir)
    status = ws.bootstrap()
    if not status["workspace_exists"] or not Path(ws.python).exists():
        raise RuntimeError("Parameter Golf workspace is not bootstrapped.")

    log_dir = logs_dir / "parameter_golf"
    log_dir.mkdir(parents=True, exist_ok=True)
    run_log_path = log_dir / f"{run_id}.txt"
    if run_log_path.exists():
        run_log_path.unlink()
    for suffix in ["_mlx_model.npz", "_mlx_model.int8.ptz"]:
        artifact = log_dir / f"{run_id}{suffix}"
        if artifact.exists():
            artifact.unlink()

    if not status["dataset_ready"]:
        _emit("dataset missing; downloading challenge data")
        dl = ws.download_dataset()
        if dl.returncode != 0:
            raise RuntimeError(f"Dataset bootstrap failed:\n{dl.stderr.strip()}")

    script_path = ws.path / "train_gpt_mlx.py"
    original = script_path.read_text()
    modified = plan.get("modified_script")
    diff_text = ""

    if modified:
        _validate_script(modified)
        diff_text = "".join(difflib.unified_diff(
            original.splitlines(keepends=True),
            modified.splitlines(keepends=True),
            fromfile="a/train_gpt_mlx.py", tofile="b/train_gpt_mlx.py",
        ))
        script_path.write_text(modified)
        _emit("modified script written")

    try:
        script_snapshot = script_path.read_text()
        env = ws.build_env(run_id)
        command = [ws.python, "train_gpt_mlx.py"]
        _emit(f"launching {run_id} track={plan.get('track', '?')}{' +modified' if modified else ''}")
        started = datetime.now(timezone.utc)
        completed = _run_command(command, ws.path, env, run_log_path)
        finished = datetime.now(timezone.utc)
    finally:
        if modified:
            script_path.write_text(original)
            _emit("original script restored")

    runtime_seconds = max((finished - started).total_seconds(), 0.0)
    run_log = run_log_path.read_text() if run_log_path.exists() else (completed.stdout + completed.stderr)

    final = _parse_final_metrics(run_log)
    quant_path = log_dir / f"{run_id}_mlx_model.int8.ptz"
    quant_bytes = quant_path.stat().st_size if quant_path.exists() else 0
    code_bytes = len(script_snapshot.encode("utf-8"))
    artifact_bytes = code_bytes + quant_bytes
    score = final["val_bpb"]

    return {
        "score": score,
        "runtime_seconds": runtime_seconds,
        "passed": completed.returncode == 0,
        "patch": diff_text,
        "run_log": run_log,
        "train_script": script_snapshot,
        "diagnostics": {
            "val_loss": final["val_loss"],
            "quantized_bytes": quant_bytes,
            "code_bytes": code_bytes,
            "artifact_bytes": artifact_bytes,
            "under_16mb": artifact_bytes <= 16_000_000,
        },
        "provenance": {
            "adapter": "parameter_golf",
            "workspace": str(ws.path),
            "command": command,
            "has_modified_script": bool(modified),
            "requirements_path": str(ws.path / "requirements.txt"),
            "quantized_model_path": str(quant_path) if quant_path.exists() else "",
            "launch_baseline_env": {k: env.get(k) for k in [
                "MAX_WALLCLOCK_SECONDS", "MLX_EAGER_EVAL",
            ]},
        },
    }


#Script validation

def _validate_script(content: str) -> None:
    lines = content.splitlines()
    if len(lines) > MAX_SCRIPT_LINES:
        raise RuntimeError(f"Modified script exceeds {MAX_SCRIPT_LINES} line limit ({len(lines)} lines)")
    compile(content, "train_gpt_mlx.py", "exec")
    for marker in REQUIRED_MARKERS:
        if marker not in content:
            raise RuntimeError(f"Missing required marker: {marker}")


#Subprocess runner

def _run_command(command: list[str], cwd: Path, env: dict, run_log_path: Path) -> subprocess.CompletedProcess:
    stdout_lines: list[str] = []
    with run_log_path.open("w") as log:
        proc = subprocess.Popen(  # noqa: S603
            command, cwd=cwd, stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT, text=True, env=env,
        )
        assert proc.stdout is not None
        for line in proc.stdout:
            stdout_lines.append(line)
            log.write(line)
            log.flush()
            text = line.strip()
            if text and text.startswith(("run_id:", "model_params:", "iterations:", "step:", "warmup_step:", "final_int8_zlib_roundtrip", "throughput:", "memory:", "WARNING:")):
                _emit(text)
        returncode = proc.wait()
    return subprocess.CompletedProcess(command, returncode, "".join(stdout_lines), "")


#Metric parsing

def _parse_final_metrics(text: str) -> dict[str, float]:
    matches = list(FINAL_EXACT_RE.finditer(text))
    if not matches:
        raise RuntimeError("Log missing final_int8_zlib_roundtrip_exact metrics.")
    m = matches[-1]
    return {"val_loss": float(m.group("val_loss")), "val_bpb": float(m.group("val_bpb"))}
