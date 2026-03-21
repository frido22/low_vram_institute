from __future__ import annotations

from datetime import datetime, timezone
import json
import os
import re
import subprocess
from pathlib import Path

from ..config import Paths
from ..models import Plan
from ..services.parameter_golf_workspace import ParameterGolfWorkspace


FINAL_EXACT_RE = re.compile(r"final_int8_zlib_roundtrip_exact val_loss:(?P<val_loss>[0-9.]+) val_bpb:(?P<val_bpb>[0-9.]+)")
STEP_RE = re.compile(r"step:(?P<step>\d+)/(?P<total>\d+).*?val_loss:(?P<val_loss>[0-9.]+) val_bpb:(?P<val_bpb>[0-9.]+)")


class ParameterGolfAdapter:
    def __init__(self, paths: Paths) -> None:
        self.paths = paths
        self.workspace = ParameterGolfWorkspace(paths)

    def run(self, run_id: str, plan: Plan) -> dict:
        status = self.workspace.bootstrap()
        if not status["workspace_exists"] or not status["python_exists"]:
            raise RuntimeError("Parameter Golf workspace is not bootstrapped.")

        log_dir = self.paths.logs_dir / "parameter_golf"
        log_dir.mkdir(parents=True, exist_ok=True)
        if not status["dataset_ready"]:
            download = self.workspace.download_dataset()
            if download.returncode != 0:
                raise RuntimeError(f"Parameter Golf dataset bootstrap failed:\n{download.stderr.strip()}")

        env = self.workspace.build_env(run_id, out_dir=log_dir)
        command = [self.workspace.python, "train_gpt_mlx.py"]
        started = datetime.now(timezone.utc)
        completed = subprocess.run(  # noqa: S603
            command,
            cwd=self.workspace.workspace,
            capture_output=True,
            text=True,
            check=False,
            env=env,
        )
        finished = datetime.now(timezone.utc)
        runtime_seconds = max((finished - started).total_seconds(), 0.0)
        run_log_path = log_dir / f"{run_id}.txt"
        run_log = run_log_path.read_text() if run_log_path.exists() else (completed.stdout + completed.stderr)

        final = self._parse_final_metrics(run_log)
        metrics_rows = self._parse_metrics_rows(run_log)
        quant_path = log_dir / f"{run_id}_mlx_model.int8.ptz"
        quant_bytes = quant_path.stat().st_size if quant_path.exists() else 0
        score = final["val_bpb"]
        summary = (
            f"Ran local MLX Parameter Golf proxy on the Mac mini track. "
            f"Final val_bpb={score:.4f}, val_loss={final['val_loss']:.4f}, quantized artifact={quant_bytes} bytes."
        )
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
        )
        patch = self._env_patch(run_id, env)
        return {
            "score": score,
            "runtime_seconds": runtime_seconds,
            "artifact_stats": {
                "files_touched": 3 if quant_bytes else 1,
                "log_lines": len(run_log.splitlines()),
                "generated_at": finished.isoformat(),
                "quantized_artifact_bytes": quant_bytes,
                "track": plan.track,
            },
            "passed": completed.returncode == 0,
            "needs_validation": plan.mode != "validate",
            "higher_is_better": False,
            "patch": patch,
            "summary": summary,
            "logs": run_log.splitlines()[-200:],
            "outputs": {
                "adapter": "parameter_golf",
                "experiment_name": "parameter_golf_mlx_local",
                "run_log": run_log,
                "metrics_jsonl": metrics_jsonl,
                "analysis_md": analysis,
                "track": plan.track,
            },
            "provenance": {
                "adapter": "parameter_golf",
                "plan_mode": plan.mode,
                "workspace": str(self.workspace.workspace),
                "command": command,
                "env_subset": {k: env[k] for k in ["RUN_ID", "OUT_DIR", "ITERATIONS", "TRAIN_BATCH_TOKENS", "VAL_BATCH_SIZE", "MAX_WALLCLOCK_SECONDS"] if k in env},
            },
        }

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

    def _env_patch(self, run_id: str, env: dict[str, str]) -> str:
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
        return "\n".join(lines) + "\n"
