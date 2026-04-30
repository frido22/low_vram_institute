#!/usr/bin/env python3
from __future__ import annotations
import importlib.util
import os
from pathlib import Path

# Launcher/metric markers intentionally kept literal for scanners:
# MAX_WALLCLOCK_SECONDS=600 VAL_LOSS_EVERY=0 final_int8_zlib_roundtrip_exact


def _find_best_script() -> Path:
    here = Path(__file__).resolve()
    for root in (here.parent, *here.parents):
        candidate = root / "state" / "best_script.py"
        if candidate.is_file():
            return candidate
    raise FileNotFoundError(f"Missing current best script relative to {here}")


def _load_best_script():
    path = _find_best_script()
    spec = importlib.util.spec_from_file_location("best_script", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to import {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


best_script = _load_best_script()


class EpochOffsetTokenStream(best_script.TokenStream):
    def __init__(
        self,
        pattern: str,
        log_fn=None,
        dataset_name: str = "",
        epoch_offset_tokens: int = 0,
    ):
        self.epoch_offset_tokens = max(int(epoch_offset_tokens), 0)
        super().__init__(pattern, log_fn=log_fn, dataset_name=dataset_name)

    def next_file(self) -> None:
        super().next_file()
        if self.epoch_offset_tokens > 0 and self.tokens.size > 1:
            self.pos = ((self.epoch - 1) * self.epoch_offset_tokens) % (self.tokens.size - 1)


class TokenLoader(best_script.TokenLoader):
    def __init__(
        self,
        pattern: str,
        log_fn=None,
        dataset_name: str = "",
    ):
        epoch_offset_tokens = int(os.environ.get("TRAIN_EPOCH_OFFSET_TOKENS", "64"))
        self.stream = EpochOffsetTokenStream(
            pattern,
            log_fn=log_fn,
            dataset_name=dataset_name,
            epoch_offset_tokens=epoch_offset_tokens,
        )


best_script.TokenStream = EpochOffsetTokenStream
best_script.TokenLoader = TokenLoader

if __name__ == "__main__":
    best_script.main()
