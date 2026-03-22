from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
import json
import re
import subprocess
from pathlib import Path
from typing import TextIO

from ..config import Paths
from ..models import Plan
from ..services.parameter_golf_workspace import ParameterGolfWorkspace


FINAL_EXACT_RE = re.compile(r"final_int8_zlib_roundtrip_exact val_loss:(?P<val_loss>[0-9.]+) val_bpb:(?P<val_bpb>[0-9.]+)")
STEP_RE = re.compile(r"step:(?P<step>\d+)/(?P<total>\d+).*?val_loss:(?P<val_loss>[0-9.]+) val_bpb:(?P<val_bpb>[0-9.]+)")
THROUGHPUT_RE = re.compile(r"throughput:avg_tok_s:(?P<avg_tok_s>[0-9.]+) total_tokens:(?P<total_tokens>\d+)")
MEMORY_RE = re.compile(r"memory:peak_mb:(?P<peak_mb>[0-9.]+) active_mb:(?P<active_mb>[0-9.]+)")

class CodePatchError(RuntimeError):
    """Raised when a code patch fails to apply or validate."""

BANNED_IMPORTS = ["socket", "http", "urllib", "requests"]
REQUIRED_MARKERS = ["final_int8_zlib_roundtrip_exact", "MAX_WALLCLOCK_SECONDS"]
MAX_PATCHED_LINES = 1500


class ParameterGolfAdapter:
    def __init__(self, paths: Paths) -> None:
        self.paths = paths
        self.workspace = ParameterGolfWorkspace(paths)

    def run(self, run_id: str, plan: Plan) -> dict:
        status = self.workspace.bootstrap()
        if not status["workspace_exists"] or not status["python_exists"]:
            raise RuntimeError("Parameter Golf workspace is not bootstrapped.")

        self._restore_backup_if_needed()

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

        with self._patched_script(plan) as patched_content:
            env = self.workspace.build_env(run_id, overrides=self._validated_overrides(plan), out_dir=log_dir)
            command = [self.workspace.python, "train_gpt_mlx.py"]
            patch_info = " +code_patch" if patched_content else ""
            self._emit(
                f"launching {run_id} track={plan.track} iterations={env.get('ITERATIONS')} "
                f"batch_tokens={env.get('TRAIN_BATCH_TOKENS')} val_batch={env.get('VAL_BATCH_SIZE')}{patch_info}"
            )
            started = datetime.now(timezone.utc)
            completed = self._run_command(command, env, run_log_path)
            finished = datetime.now(timezone.utc)

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
        if patched_content:
            summary += f" Code patch applied ({len(plan.code_patch or [])} edits)."
        if diagnostics.get("avg_tok_s"):
            summary += f" Throughput: {diagnostics['avg_tok_s']:.0f} tok/s."
        if diagnostics.get("peak_mb"):
            summary += f" Memory: {diagnostics['peak_mb']:.0f}MB peak, {diagnostics.get('active_mb', 0):.0f}MB active."
        metrics_jsonl = "\n".join(json.dumps(row, sort_keys=True) for row in metrics_rows)
        analysis = (
            "# Analysis\n\n"
            f"- Track: {plan.track}\n"
            f"- Workspace: {self.workspace.workspace}\n"
            f"- Runtime seconds: {runtime_seconds:.2f}\n"
            f"- Final val_bpb: {score:.4f}\n"
            f"- Final val_loss: {final['val_loss']:.4f}\n"
            f"- Quantized artifact bytes: {quant_bytes}\n"
            f"- Step metrics captured: {len(metrics_rows)}\n"
            f"- Env overrides: {json.dumps(plan.env_overrides, sort_keys=True)}\n"
            f"- Code patch: {'yes' if patched_content else 'no'}\n"
        )
        if diagnostics.get("avg_tok_s"):
            analysis += f"- Throughput: {diagnostics['avg_tok_s']:.0f} tok/s ({diagnostics.get('total_tokens', 0)} total tokens)\n"
        if diagnostics.get("peak_mb"):
            analysis += f"- Memory: {diagnostics['peak_mb']:.0f}MB peak, {diagnostics.get('active_mb', 0):.0f}MB active\n"
        patch = self._run_patch(run_id, env, plan.code_patch)
        outputs = {
            "adapter": "parameter_golf",
            "experiment_name": "parameter_golf_mlx_local",
            "run_log": run_log,
            "metrics_jsonl": metrics_jsonl,
            "analysis_md": analysis,
            "track": plan.track,
        }
        return {
            "score": score,
            "runtime_seconds": runtime_seconds,
            "artifact_stats": {
                "files_touched": 3 if quant_bytes else 1,
                "log_lines": len(run_log.splitlines()),
                "generated_at": finished.isoformat(),
                "quantized_artifact_bytes": quant_bytes,
                "track": plan.track,
                "env_overrides": dict(plan.env_overrides),
                "has_code_patch": bool(plan.code_patch),
            },
            "passed": completed.returncode == 0,
            "needs_validation": plan.mode != "validate",
            "higher_is_better": False,
            "patch": patch,
            "summary": summary,
            "logs": run_log.splitlines()[-200:],
            "outputs": outputs,
            "provenance": {
                "adapter": "parameter_golf",
                "plan_mode": plan.mode,
                "workspace": str(self.workspace.workspace),
                "command": command,
                "env_subset": {k: env[k] for k in ["RUN_ID", "OUT_DIR", "ITERATIONS", "TRAIN_BATCH_TOKENS", "VAL_BATCH_SIZE", "MAX_WALLCLOCK_SECONDS"] if k in env},
                "env_overrides": dict(plan.env_overrides),
                "has_code_patch": bool(plan.code_patch),
            },
        }

    # --- Code patch lifecycle ---

    @contextmanager
    def _patched_script(self, plan: Plan):
        """Apply code_patch before run, always restore after."""
        script_path = self._script_path()
        original_content = script_path.read_text()
        backup_path = self._backup_path()
        patched_content = None

        if plan.code_patch:
            backup_path.write_text(original_content)
            try:
                patched_content = self._apply_patch(original_content, plan.code_patch)
                self._validate_patched_script(patched_content)
                script_path.write_text(patched_content)
                self._emit("code patch applied successfully")
            except Exception as exc:
                script_path.write_text(original_content)
                backup_path.unlink(missing_ok=True)
                raise CodePatchError(str(exc)) from exc
        try:
            yield patched_content
        finally:
            script_path.write_text(original_content)
            backup_path.unlink(missing_ok=True)
            if plan.code_patch:
                self._emit("code patch reverted")

    def _script_path(self) -> Path:
        return Path(self.workspace.workspace) / "train_gpt_mlx.py"

    def _backup_path(self) -> Path:
        return Path(self.workspace.workspace) / "train_gpt_mlx.py.backup"

    def _restore_backup_if_needed(self) -> None:
        """Crash recovery: restore original if a backup was left behind."""
        backup = self._backup_path()
        script = self._script_path()
        if backup.exists():
            self._emit("found leftover backup from previous crash, restoring original script")
            script.write_text(backup.read_text())
            backup.unlink()

    def _apply_patch(self, original: str, edits: list[dict[str, str]]) -> str:
        """Apply search-and-replace edits and return the patched content."""
        content = original
        for i, edit in enumerate(edits):
            old = edit.get("old", "")
            new = edit.get("new", "")
            if not old:
                raise RuntimeError(f"edit {i}: empty 'old' string")
            count = content.count(old)
            if count == 0:
                raise RuntimeError(f"edit {i}: 'old' string not found in script")
            if count > 1:
                raise RuntimeError(f"edit {i}: 'old' string matches {count} times (must be unique)")
            content = content.replace(old, new, 1)
        return content

    def _validate_patched_script(self, content: str) -> None:
        """Static safety checks on patched script before running."""
        lines = content.splitlines()
        if len(lines) > MAX_PATCHED_LINES:
            raise RuntimeError(f"Patched script exceeds {MAX_PATCHED_LINES} line limit ({len(lines)} lines)")

        compile(content, "train_gpt_mlx.py", "exec")

        for i, line in enumerate(lines, 1):
            stripped = line.strip()
            for mod in BANNED_IMPORTS:
                if stripped.startswith(f"import {mod}") or stripped.startswith(f"from {mod}"):
                    raise RuntimeError(f"Banned import '{mod}' at line {i}")

        for marker in REQUIRED_MARKERS:
            if marker not in content:
                raise RuntimeError(f"Patched script is missing required marker: {marker}")

    # --- Override validation ---

    def _validated_overrides(self, plan: Plan) -> dict[str, str]:
        policy = self.workspace.runtime.get("mutation_policy", {})
        allowed = policy.get("allowed_env", {})
        fixed = {str(k): str(v) for k, v in policy.get("fixed_env", {}).items()}
        overrides = {str(k): str(v) for k, v in (plan.env_overrides or {}).items()}
        validated: dict[str, str] = {}
        disallowed_keys = {"DATA_PATH", "TOKENIZER_PATH", "OUT_DIR", "RUN_ID", "VOCAB_SIZE"}

        for key, value in overrides.items():
            if key in disallowed_keys:
                raise RuntimeError(f"Illegal Parameter Golf override: {key}")
            if key in fixed and value != fixed[key]:
                raise RuntimeError(f"Fixed Parameter Golf constraint violated: {key} must remain {fixed[key]}")
            spec = allowed.get(key)
            if spec is None:
                raise RuntimeError(f"Unsupported Parameter Golf override: {key}")
            validated[key] = self._validate_override_value(key, value, spec)

        validated.update(fixed)
        return validated

    def _validate_override_value(self, key: str, value: str, spec: dict) -> str:
        kind = spec.get("type")
        if kind == "choice":
            values = [str(item) for item in spec.get("values", [])]
            if value not in values:
                raise RuntimeError(f"Illegal value for {key}: {value}")
            return value
        if kind == "int":
            try:
                parsed = int(value)
            except ValueError as exc:
                raise RuntimeError(f"Illegal integer value for {key}: {value}") from exc
            minimum = int(spec.get("min", parsed))
            maximum = int(spec.get("max", parsed))
            step = int(spec.get("step", 1))
            if parsed < minimum or parsed > maximum:
                raise RuntimeError(f"Illegal value for {key}: {value}")
            if (parsed - minimum) % step != 0:
                raise RuntimeError(f"Illegal step for {key}: {value}")
            return str(parsed)
        raise RuntimeError(f"Unknown mutation policy type for {key}: {kind}")

    # --- Execution helpers ---

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
            for line in process.stdout:
                stdout_lines.append(line)
                log_handle.write(line)
                log_handle.flush()
                self._maybe_emit_live_line(line, log_handle)
            returncode = process.wait()
        return subprocess.CompletedProcess(command, returncode, "".join(stdout_lines), "")

    def _maybe_emit_live_line(self, line: str, _log_handle: TextIO) -> None:
        text = line.strip()
        if not text:
            return
        if text.startswith(("run_id:", "model_params:", "iterations:", "step:", "warmup_step:", "final_int8_zlib_roundtrip", "throughput:", "memory:", "WARNING:")):
            self._emit(text)

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

    # --- Patch artifact generation ---

    def _run_patch(self, run_id: str, env: dict[str, str], code_patch: list[dict[str, str]] | None) -> str:
        lines = [
            "diff --git a/parameter_golf_env.txt b/parameter_golf_env.txt",
            "new file mode 100644",
            "--- /dev/null",
            "+++ b/parameter_golf_env.txt",
            f"+run_id={run_id}",
        ]
        for key in sorted(["ITERATIONS", "TRAIN_BATCH_TOKENS", "VAL_BATCH_SIZE", "VAL_LOSS_EVERY", "TRAIN_LOG_EVERY", "MLX_EAGER_EVAL", "MAX_WALLCLOCK_SECONDS"]):
            if key in env:
                lines.append(f"+{key}={env[key]}")
        if code_patch:
            lines.append("")
            lines.append("# --- code patch applied to train_gpt_mlx.py ---")
            for i, edit in enumerate(code_patch):
                lines.append(f"# edit {i}: replace {len(edit.get('old', ''))} chars -> {len(edit.get('new', ''))} chars")
                lines.append(json.dumps(edit, ensure_ascii=False))
        return "\n".join(lines) + "\n"
