from __future__ import annotations

from datetime import datetime, timezone
import difflib
import json
import re
import subprocess
import time
from pathlib import Path
from typing import TextIO

from ..config import Paths
from ..models import Plan
from ..services.parameter_golf_workspace import ParameterGolfWorkspace


FINAL_EXACT_RE = re.compile(r"final_int8_zlib_roundtrip_exact val_loss:(?P<val_loss>[0-9.]+) val_bpb:(?P<val_bpb>[0-9.]+)")
STEP_RE = re.compile(r"step:(?P<step>\d+)/(?P<total>\d+).*?val_loss:(?P<val_loss>[0-9.]+) val_bpb:(?P<val_bpb>[0-9.]+)")
THROUGHPUT_RE = re.compile(r"throughput:avg_tok_s:(?P<avg_tok_s>[0-9.]+) total_tokens:(?P<total_tokens>\d+)")
MEMORY_RE = re.compile(r"memory:peak_mb:(?P<peak_mb>[0-9.]+) active_mb:(?P<active_mb>[0-9.]+)")

BANNED_IMPORTS = ["socket", "http", "urllib", "requests"]
REQUIRED_MARKERS = ["final_int8_zlib_roundtrip_exact", "MAX_WALLCLOCK_SECONDS"]
MAX_SCRIPT_LINES = 1500


class ParameterGolfAdapter:
    higher_is_better: bool = False  # Parameter Golf: lower score is better

    def __init__(self, paths: Paths) -> None:
        self.paths = paths
        self.workspace = ParameterGolfWorkspace(paths)

    def run(self, run_id: str, plan: Plan) -> dict:
        status = self.workspace.bootstrap()
        if not status["workspace_exists"] or not status["python_exists"]:
            raise RuntimeError("Parameter Golf workspace is not bootstrapped.")

        log_dir = self.paths.logs_dir / "parameter_golf"
        log_dir.mkdir(parents=True, exist_ok=True)
        run_log_path = log_dir / f"{run_id}.txt"
        if run_log_path.exists():
            run_log_path.unlink()
        for suffix in ["_mlx_model.npz", "_mlx_model.int8.ptz"]:
            artifact = log_dir / f"{run_id}{suffix}"
            if artifact.exists():
                artifact.unlink()
        if not status["dataset_ready"]:
            self._emit("dataset missing; downloading challenge data")
            download = self.workspace.download_dataset()
            if download.returncode != 0:
                raise RuntimeError(f"Parameter Golf dataset bootstrap failed:\n{download.stderr.strip()}")

        script_path = self._script_path()
        original = script_path.read_text()
        modified = plan.modified_script
        diff_text = ""

        if modified:
            self._validate_script(modified)
            diff_text = self._compute_diff(original, modified)
            script_path.write_text(modified)
            self._emit("modified script written")

        try:
            script_snapshot = script_path.read_text()
            env = self.workspace.build_env(run_id, out_dir=log_dir)
            command = [self.workspace.python, "train_gpt_mlx.py"]
            self._emit(f"launching {run_id} track={plan.track}{' +modified' if modified else ''}")
            started = datetime.now(timezone.utc)
            completed = self._run_command(command, env, run_log_path)
            finished = datetime.now(timezone.utc)
        finally:
            # Always restore original
            if modified:
                script_path.write_text(original)
                self._emit("original script restored")

        runtime_seconds = max((finished - started).total_seconds(), 0.0)
        run_log = run_log_path.read_text() if run_log_path.exists() else (completed.stdout + completed.stderr)

        final = self._parse_final_metrics(run_log)
        metrics_rows = self._parse_metrics_rows(run_log)
        diagnostics = self._parse_diagnostics(run_log)
        quant_path = log_dir / f"{run_id}_mlx_model.int8.ptz"
        quant_bytes = quant_path.stat().st_size if quant_path.exists() else 0
        score = final["val_bpb"]
        summary = (
            f"Ran local MLX Parameter Golf in official-like mode on the Mac mini. "
            f"Final val_bpb={score:.4f}, val_loss={final['val_loss']:.4f}, quantized artifact={quant_bytes} bytes."
        )
        if modified:
            summary += " Modified script used."
        if diagnostics.get("avg_tok_s"):
            summary += f" Throughput: {diagnostics['avg_tok_s']:.0f} tok/s."
        if diagnostics.get("peak_mb"):
            summary += f" Memory: {diagnostics['peak_mb']:.0f}MB peak, {diagnostics.get('active_mb', 0):.0f}MB active."
        metrics_jsonl = "\n".join(json.dumps(row, sort_keys=True) for row in metrics_rows)
        outputs = {
            "run_log": run_log,
            "metrics_jsonl": metrics_jsonl,
            "track": plan.track,
            "train_script": script_snapshot,
        }
        return {
            "score": score,
            "runtime_seconds": runtime_seconds,
            "artifact_stats": {
                "generated_at": finished.isoformat(),
                "quantized_artifact_bytes": quant_bytes,
                "track": plan.track,
                "has_modified_script": bool(modified),
            },
            "passed": completed.returncode == 0,
            "needs_validation": plan.mode != "validate",
            "higher_is_better": self.higher_is_better,
            "patch": diff_text,
            "summary": summary,
            "outputs": outputs,
            "provenance": {
                "adapter": "parameter_golf",
                "plan_mode": plan.mode,
                "workspace": str(self.workspace.workspace),
                "command": command,
                "has_modified_script": bool(modified),
            },
        }

    # --- Script validation ---

    def _validate_script(self, content: str) -> None:
        """Validate modified script before running."""
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
                raise RuntimeError(f"Modified script is missing required marker: {marker}")

    # --- Diff computation ---

    @staticmethod
    def _compute_diff(original: str, modified: str) -> str:
        """Compute a unified diff (GitHub-style) between original and modified."""
        return "".join(difflib.unified_diff(
            original.splitlines(keepends=True),
            modified.splitlines(keepends=True),
            fromfile="a/train_gpt_mlx.py",
            tofile="b/train_gpt_mlx.py",
        ))

    # --- Helpers ---

    def _script_path(self) -> Path:
        return Path(self.workspace.workspace) / "train_gpt_mlx.py"

    def _emit(self, message: str) -> None:
        print(f"[parameter_golf] {message}", flush=True)

    def _run_command(self, command: list[str], env: dict[str, str], run_log_path) -> subprocess.CompletedProcess:
        stdout_lines: list[str] = []
        with run_log_path.open("w") as log_handle:
            process = subprocess.Popen(  # noqa: S603
                command,
                cwd=self.workspace.workspace,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                env=env,
            )
            assert process.stdout is not None
            peak_rss_mb = 0.0
            last_rss_sample_at = 0.0
            for line in process.stdout:
                stdout_lines.append(line)
                log_handle.write(line)
                log_handle.flush()
                now = time.monotonic()
                if now - last_rss_sample_at >= 1.0:
                    peak_rss_mb = max(peak_rss_mb, self._sample_rss_mb(process.pid))
                    last_rss_sample_at = now
                self._maybe_emit_live_line(line, log_handle)
            returncode = process.wait()
            peak_rss_mb = max(peak_rss_mb, self._sample_rss_mb(process.pid))
            if peak_rss_mb > 0:
                memory_line = f"memory:peak_mb:{peak_rss_mb:.1f} active_mb:{peak_rss_mb:.1f}\n"
                stdout_lines.append(memory_line)
                log_handle.write(memory_line)
                log_handle.flush()
                self._emit(memory_line.strip())
        return subprocess.CompletedProcess(command, returncode, "".join(stdout_lines), "")

    def _maybe_emit_live_line(self, line: str, _log_handle: TextIO) -> None:
        text = line.strip()
        if not text:
            return
        if text.startswith(("run_id:", "model_params:", "iterations:", "step:", "warmup_step:", "final_int8_zlib_roundtrip", "throughput:", "memory:", "WARNING:")):
            self._emit(text)

    def _sample_rss_mb(self, pid: int) -> float:
        completed = subprocess.run(  # noqa: S603
            ["ps", "-o", "rss=", "-p", str(pid)],
            capture_output=True,
            text=True,
            check=False,
        )
        if completed.returncode != 0:
            return 0.0
        try:
            rss_kb = int(completed.stdout.strip() or "0")
        except ValueError:
            return 0.0
        return rss_kb / 1024.0

    # --- Metric parsing ---

    def _parse_final_metrics(self, text: str) -> dict[str, float]:
        matches = list(FINAL_EXACT_RE.finditer(text))
        if not matches:
            raise RuntimeError("Parameter Golf log did not contain final_int8_zlib_roundtrip_exact metrics.")
        match = matches[-1]
        return {"val_loss": float(match.group("val_loss")), "val_bpb": float(match.group("val_bpb"))}

    def _parse_metrics_rows(self, text: str) -> list[dict[str, float]]:
        rows: list[dict[str, float]] = []
        for line in text.splitlines():
            match = STEP_RE.search(line)
            if not match:
                continue
            rows.append(
                {
                    "step": float(match.group("step")),
                    "total_steps": float(match.group("total")),
                    "val_loss": float(match.group("val_loss")),
                    "val_bpb": float(match.group("val_bpb")),
                }
            )
        return rows

    def _parse_diagnostics(self, text: str) -> dict[str, float]:
        result: dict[str, float] = {}
        match = THROUGHPUT_RE.search(text)
        if match:
            result["avg_tok_s"] = float(match.group("avg_tok_s"))
            result["total_tokens"] = float(match.group("total_tokens"))
        match = MEMORY_RE.search(text)
        if match:
            result["peak_mb"] = float(match.group("peak_mb"))
            result["active_mb"] = float(match.group("active_mb"))
        return result
