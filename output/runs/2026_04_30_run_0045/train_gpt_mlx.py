#!/usr/bin/env python3
from __future__ import annotations
from pathlib import Path

# Launcher/metric markers kept literal for preflight scanners:
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
    '    tail_recur_stage_span: float = float(os.environ.get("TAIL_RECUR_STAGE_SPAN", 0.12))\n',
    '    tail_recur_stage_span: float = float(os.environ.get("TAIL_RECUR_STAGE_SPAN", 0.12))\n    tail_recur_quant_min_gain: float = float(os.environ.get("TAIL_RECUR_QUANT_MIN_GAIN", 0.72))\n',
)
code = _replace_once(
    code,
    '''def main() -> None:\n''',
    '''def tail_recur_train_gains(args: Hyperparameters, step: int, active_blocks: int, quant_aware_active: bool) -> mx.array:\n    gains = tail_recur_schedule(args, step, active_blocks)\n    if quant_aware_active and active_blocks > 1 and args.tail_recur_quant_min_gain > args.tail_recur_min_gain:\n        floor = np.linspace(args.tail_recur_quant_min_gain, 1.0, active_blocks, dtype=np.float32)\n        gains = mx.maximum(gains, mx.array(floor, dtype=mx.float32))\n    return gains\ndef main() -> None:\n''',
)
code = _replace_once(
    code,
    '    log(f"tail_recur_staging:gap:{args.tail_recur_stage_gap} span:{args.tail_recur_stage_span}")\n',
    '    log(f"tail_recur_staging:gap:{args.tail_recur_stage_gap} span:{args.tail_recur_stage_span}")\n    log(f"tail_recur_endgame:quant_min_gain:{args.tail_recur_quant_min_gain}")\n',
)
code = _replace_once(
    code,
    '        tail_recur_gains = tail_recur_schedule(args, step, args.tail_recur_blocks)\n',
    '        tail_recur_gains = tail_recur_train_gains(args, step, args.tail_recur_blocks, quant_aware_active)\n',
)
globals()["__patched_source__"] = code
exec(compile(code, str(Path(__file__).resolve()), "exec"), globals(), globals())
