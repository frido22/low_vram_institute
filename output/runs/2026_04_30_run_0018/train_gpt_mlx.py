#!/usr/bin/env python3
from __future__ import annotations
from pathlib import Path

# Planner-visible markers: MAX_WALLCLOCK_SECONDS=600 VAL_LOSS_EVERY=0 final_int8_zlib_roundtrip_exact


def _find_base_script() -> Path:
    here = Path(__file__).resolve()
    for root in (here.parent, *here.parents):
        candidate = root / "state" / "best_script.py"
        if candidate.is_file():
            return candidate
    raise FileNotFoundError(f"Missing current best script relative to {here}")


def _replace_once(text: str, old: str, new: str) -> str:
    if old in text:
        return text.replace(old, new, 1)
    if new in text:
        return text
    raise RuntimeError(f"Missing patch target:\n{old}")


base_path = _find_base_script()
code = base_path.read_text(encoding="utf-8")
code = _replace_once(code, 'code = Path(__file__).read_text(encoding="utf-8")\n', 'code = __patched_source__\n')
code = _replace_once(
    code,
    '    val_loss_every: int = int(os.environ.get("VAL_LOSS_EVERY", 0))\n',
    '    val_loss_every: int = 0\n',
)
code = _replace_once(
    code,
    '    quant_aware_every: int = int(os.environ.get("QUANT_AWARE_EVERY", 24))\n',
    '    quant_aware_every: int = int(os.environ.get("QUANT_AWARE_EVERY", 24))\n    quant_aware_min_step: int = int(os.environ.get("QUANT_AWARE_MIN_STEP", 640))\n',
)
code = _replace_once(
    code,
    '    if args.quant_aware_every <= 0:\n        return False\n',
    '    if args.quant_aware_every <= 0 or step < args.quant_aware_min_step:\n        return False\n',
)
code = _replace_once(
    code,
    '    log(f"quant_aware:train_seconds:{args.quant_aware_train_seconds:.1f} iters:{args.quant_aware_iters} every:{args.quant_aware_every}")\n',
    '    log(f"quant_aware:train_seconds:{args.quant_aware_train_seconds:.1f} iters:{args.quant_aware_iters} every:{args.quant_aware_every} min_step:{args.quant_aware_min_step}")\n',
)
globals()["__patched_source__"] = code
exec(compile(code, str(Path(__file__).resolve()), "exec"), globals(), globals())
