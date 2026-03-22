from __future__ import annotations

from dataclasses import dataclass
import json
import subprocess
import tempfile
from pathlib import Path
from shutil import which
from typing import Any, Optional


@dataclass
class CodexStatus:
    configured: bool
    binary: Optional[str]
    note: str


class CodexInvocationError(RuntimeError):
    def __init__(self, message: str, retryable: bool, detail: str = "") -> None:
        super().__init__(message)
        self.retryable = retryable
        self.detail = detail


class CodexWrapper:
    def detect(self) -> CodexStatus:
        binary = which("codex")
        if binary:
            return CodexStatus(True, binary, "Local Codex CLI detected.")
        return CodexStatus(
            False,
            None,
            "Codex CLI not found in PATH. v1 keeps the wrapper local but does not hard-fail without the binary.",
        )

    def plan(self, workspace: Path, prompt: str, model: Optional[str] = None) -> dict[str, Any]:
        status = self.detect()
        if not status.configured or not status.binary:
            raise CodexInvocationError("Codex CLI is unavailable.", retryable=True, detail=status.note)

        schema = {
            "type": "object",
            "required": ["mode", "title", "rationale", "expected_signal", "public_updates", "adapter", "idea_source"],
            "properties": {
                "mode": {"type": "string"},
                "title": {"type": "string"},
                "rationale": {"type": "string"},
                "expected_signal": {"type": "string"},
                "public_updates": {"type": "array", "items": {"type": "string"}},
                "adapter": {"type": "string"},
                "logging_focus": {"type": "array", "items": {"type": "string"}},
                "idea_source": {"type": ["string", "null"]},
            },
            "additionalProperties": False,
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            schema_path = tmp / "planner_schema.json"
            output_path = tmp / "planner_output.json"
            schema_path.write_text(json.dumps(schema))

            command = [
                status.binary,
                "exec",
                "--skip-git-repo-check",
                "--cd",
                str(workspace),
                "--output-schema",
                str(schema_path),
                "--output-last-message",
                str(output_path),
                "--color",
                "never",
            ]
            if model:
                command.extend(["--model", model])

            completed = subprocess.run(  # noqa: S603
                command,
                input=prompt,
                capture_output=True,
                text=True,
                check=False,
            )
            if completed.returncode != 0:
                detail = "\n".join(filter(None, [completed.stdout.strip(), completed.stderr.strip()]))
                raise CodexInvocationError(
                    "Codex planning invocation failed.",
                    retryable=self._is_retryable(detail),
                    detail=detail,
                )
            if not output_path.exists():
                raise CodexInvocationError(
                    "Codex planning invocation produced no output.",
                    retryable=True,
                    detail=completed.stdout.strip(),
                )
            try:
                return json.loads(output_path.read_text())
            except json.JSONDecodeError as exc:
                raise CodexInvocationError(
                    "Codex planning output was not valid JSON.",
                    retryable=True,
                    detail=str(exc),
                ) from exc

    def _is_retryable(self, detail: str) -> bool:
        text = detail.lower()
        retryable_markers = [
            "rate limit",
            "quota",
            "temporar",
            "timeout",
            "timed out",
            "unavailable",
            "overloaded",
            "try again",
            "connection reset",
            "network",
            "429",
            "503",
            "login required",
            "not authenticated",
            "expired",
        ]
        return any(marker in text for marker in retryable_markers)
