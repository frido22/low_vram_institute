#!/usr/bin/env python3
from __future__ import annotations
from pathlib import Path

# Launcher/metric markers intentionally kept literal for scanners:
# MAX_WALLCLOCK_SECONDS=600 VAL_LOSS_EVERY=0 final_int8_zlib_roundtrip_exact


def _find_base_script() -> Path:
    here = Path(__file__).resolve()
    for root in (here.parent, *here.parents):
        candidate = root / "state" / "best_script.py"
        if candidate.is_file():
            return candidate
    raise FileNotFoundError(f"Missing current best script relative to {here}")


def _replace_once(text: str, old: str, new: str) -> str:
    if old not in text:
        raise RuntimeError(f"Missing patch target:\n{old}")
    return text.replace(old, new, 1)


code = _find_base_script().read_text(encoding="utf-8")
code = _replace_once(code, 'code = Path(__file__).read_text(encoding="utf-8")\n', 'code = __patched_source__\n')
code = _replace_once(
    code,
    '    for block_idx in range(max(num_layers - tail_recur_blocks, 0), num_layers):\n        prefix = f"blocks.{block_idx}."\n        keep.update(prefix + suffix for suffix in BLOCK_FP16_MATRIX_SUFFIXES[:2])\n    if num_layers > 0:\n        prefix = f"blocks.{num_layers - 1}."\n        keep.update(prefix + suffix for suffix in BLOCK_FP16_MATRIX_SUFFIXES[2:3])\n    return keep\n',
    '    for block_idx in range(max(num_layers - tail_recur_blocks, 0), num_layers):\n        prefix = f"blocks.{block_idx}."\n        keep.update(prefix + suffix for suffix in BLOCK_FP16_MATRIX_SUFFIXES[:3])\n    return keep\n',
)
globals()["__patched_source__"] = code
exec(compile(code, str(Path(__file__).resolve()), "exec"), globals(), globals())
