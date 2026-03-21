from __future__ import annotations

from dataclasses import dataclass
from shutil import which
from typing import Optional


@dataclass
class CodexStatus:
    configured: bool
    binary: Optional[str]
    note: str


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
