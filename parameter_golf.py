"""Parameter Golf adapter — runs train_gpt_mlx.py, captures metrics."""
from __future__ import annotations

from datetime import datetime, timezone
import difflib
import json
import os
import re
import subprocess
import time
from pathlib import Path


FINAL_EXACT_RE = re.compile(r"final_int8_zlib_roundtrip_exact val_loss:(?P<val_loss>[0-9.]+) val_bpb:(?P<val_bpb>[0-9.]+)")
STEP_RE = re.compile(r"step:(?P<step>\d+)/(?P<total>\d+).*?val_loss:(?P<val_loss>[0-9.]+) val_bpb:(?P<val_bpb>[0-9.]+)")
THROUGHPUT_RE = re.compile(r"throughput:avg_tok_s:(?P<avg_tok_s>[0-9.]+) total_tokens:(?P<total_tokens>\d+)")
MEMORY_RE = re.compile(r"memory:peak_mb:(?P<peak_mb>[0-9.]+) active_mb:(?P<active_mb>[0-9.]+)")

BANNED_IMPORTS = ["socket", "http", "urllib", "requests"]
REQUIRED_MARKERS = ["final_int8_zlib_roundtrip_exact", "MAX_WALLCLOCK_SECONDS"]
MAX_SCRIPT_LINES = 1500


def _emit(message: str) -> None:
    print(f"[parameter_golf] {message}", flush=True)


# ---------------------------------------------------------------------------
# Workspace helpers (merged from parameter_golf_workspace.py)
# ---------------------------------------------------------------------------

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
        env.setdefault("ITERATIONS", str(self.config.get("iterations", 200)))
        env.setdefault("TRAIN_BATCH_TOKENS", str(self.config.get("train_batch_tokens", 8192)))
        env.setdefault("VAL_BATCH_SIZE", str(self.config.get("val_batch_size", 8192)))
        env.setdefault("VAL_LOSS_EVERY", str(self.config.get("val_loss_every", 0)))
        env.setdefault("TRAIN_LOG_EVERY", str(self.config.get("train_log_every", 25)))
        env.setdefault("MAX_WALLCLOCK_SECONDS", str(self.config.get("max_wallclock_seconds", 600)))
        env.setdefault("MLX_EAGER_EVAL", str(int(bool(self.config.get("mlx_eager_eval", True)))))
        env.setdefault("MLX_MAX_MICROBATCH_TOKENS", str(self.config.get("mlx_max_microbatch_tokens", 8192)))
        return env


# ---------------------------------------------------------------------------
# Adapter
# ---------------------------------------------------------------------------

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
    metrics_rows = _parse_metrics_rows(run_log)
    diagnostics = _parse_diagnostics(run_log)
    quant_path = log_dir / f"{run_id}_mlx_model.int8.ptz"
    quant_bytes = quant_path.stat().st_size if quant_path.exists() else 0
    score = final["val_bpb"]

    summary = (
        f"Final val_bpb={score:.4f}, val_loss={final['val_loss']:.4f}, "
        f"quantized={quant_bytes}B."
    )
    if modified:
        summary += " Modified script."
    if diagnostics.get("avg_tok_s"):
        summary += f" {diagnostics['avg_tok_s']:.0f} tok/s."
    if diagnostics.get("peak_mb"):
        summary += f" {diagnostics['peak_mb']:.0f}MB peak."

    metrics_jsonl = "\n".join(json.dumps(row, sort_keys=True) for row in metrics_rows)

    return {
        "score": score,
        "runtime_seconds": runtime_seconds,
        "passed": completed.returncode == 0,
        "patch": diff_text,
        "summary": summary,
        "run_log": run_log,
        "metrics_jsonl": metrics_jsonl,
        "train_script": script_snapshot,
        "diagnostics": {
            "step_count": len(metrics_rows),
            "total_steps": int(metrics_rows[-1]["total_steps"]) if metrics_rows else 0,
            "val_loss": final["val_loss"],
            "avg_tok_s": diagnostics.get("avg_tok_s"),
            "total_tokens": diagnostics.get("total_tokens"),
            "peak_mb": diagnostics.get("peak_mb"),
            "active_mb": diagnostics.get("active_mb"),
            "quantized_bytes": quant_bytes,
        },
        "provenance": {
            "adapter": "parameter_golf",
            "workspace": str(ws.path),
            "command": command,
            "has_modified_script": bool(modified),
            "launch_baseline_env": {k: env.get(k) for k in [
                "ITERATIONS", "TRAIN_BATCH_TOKENS", "VAL_BATCH_SIZE",
                "VAL_LOSS_EVERY", "TRAIN_LOG_EVERY", "MAX_WALLCLOCK_SECONDS",
                "MLX_EAGER_EVAL", "MLX_MAX_MICROBATCH_TOKENS",
            ]},
        },
    }


# ---------------------------------------------------------------------------
# Script validation
# ---------------------------------------------------------------------------

def _validate_script(content: str) -> None:
    lines = content.splitlines()
    if len(lines) > MAX_SCRIPT_LINES:
        raise RuntimeError(f"Modified script exceeds {MAX_SCRIPT_LINES} line limit ({len(lines)} lines)")
    compile(content, "train_gpt_mlx.py", "exec")
    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        for mod in BANNED_IMPORTS:
            if stripped.startswith(f"import {mod}") or stripped.startswith(f"from {mod}"):
                raise RuntimeError(f"Banned import '{mod}' at line {i}")
    for marker in REQUIRED_MARKERS:
        if marker not in content:
            raise RuntimeError(f"Missing required marker: {marker}")


# ---------------------------------------------------------------------------
# Subprocess runner
# ---------------------------------------------------------------------------

def _run_command(command: list[str], cwd: Path, env: dict, run_log_path: Path) -> subprocess.CompletedProcess:
    stdout_lines: list[str] = []
    with run_log_path.open("w") as log:
        proc = subprocess.Popen(  # noqa: S603
            command, cwd=cwd, stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT, text=True, env=env,
        )
        assert proc.stdout is not None
        peak_rss_mb = 0.0
        last_sample = 0.0
        for line in proc.stdout:
            stdout_lines.append(line)
            log.write(line)
            log.flush()
            now = time.monotonic()
            if now - last_sample >= 1.0:
                peak_rss_mb = max(peak_rss_mb, _sample_rss(proc.pid))
                last_sample = now
            text = line.strip()
            if text and text.startswith(("run_id:", "model_params:", "iterations:", "step:", "warmup_step:", "final_int8_zlib_roundtrip", "throughput:", "memory:", "WARNING:")):
                _emit(text)
        returncode = proc.wait()
        peak_rss_mb = max(peak_rss_mb, _sample_rss(proc.pid))
        if peak_rss_mb > 0:
            mem_line = f"memory:peak_mb:{peak_rss_mb:.1f} active_mb:{peak_rss_mb:.1f}\n"
            stdout_lines.append(mem_line)
            log.write(mem_line)
            _emit(mem_line.strip())
    return subprocess.CompletedProcess(command, returncode, "".join(stdout_lines), "")


def _sample_rss(pid: int) -> float:
    r = subprocess.run(["ps", "-o", "rss=", "-p", str(pid)], capture_output=True, text=True, check=False)  # noqa: S603
    if r.returncode != 0:
        return 0.0
    try:
        return int(r.stdout.strip() or "0") / 1024.0
    except ValueError:
        return 0.0


# ---------------------------------------------------------------------------
# Metric parsing
# ---------------------------------------------------------------------------

def _parse_final_metrics(text: str) -> dict[str, float]:
    matches = list(FINAL_EXACT_RE.finditer(text))
    if not matches:
        raise RuntimeError("Log missing final_int8_zlib_roundtrip_exact metrics.")
    m = matches[-1]
    return {"val_loss": float(m.group("val_loss")), "val_bpb": float(m.group("val_bpb"))}


def _parse_metrics_rows(text: str) -> list[dict[str, float]]:
    rows = []
    for line in text.splitlines():
        m = STEP_RE.search(line)
        if m:
            rows.append({
                "step": float(m.group("step")), "total_steps": float(m.group("total")),
                "val_loss": float(m.group("val_loss")), "val_bpb": float(m.group("val_bpb")),
            })
    return rows


def _parse_diagnostics(text: str) -> dict[str, float]:
    result: dict[str, float] = {}
    m = THROUGHPUT_RE.search(text)
    if m:
        result["avg_tok_s"] = float(m.group("avg_tok_s"))
        result["total_tokens"] = float(m.group("total_tokens"))
    m = MEMORY_RE.search(text)
    if m:
        result["peak_mb"] = float(m.group("peak_mb"))
        result["active_mb"] = float(m.group("active_mb"))
    return result
