#!/usr/bin/env python3
from __future__ import annotations
from pathlib import Path

# Launcher/metric markers intentionally kept literal for the planner scanner:
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


base_path = _find_base_script()
code = base_path.read_text(encoding="utf-8")
code = _replace_once(code, 'code = Path(__file__).read_text(encoding="utf-8")\n', 'code = __patched_source__\n')
code = _replace_once(
    code,
    '    tail_recur_stage_span: float = float(os.environ.get("TAIL_RECUR_STAGE_SPAN", 0.12))\n    beta1: float = float(os.environ.get("BETA1", 0.9))\n',
    '    tail_recur_stage_span: float = float(os.environ.get("TAIL_RECUR_STAGE_SPAN", 0.12))\n    tail_recur_pulse_every: int = int(os.environ.get("TAIL_RECUR_PULSE_EVERY", 8))\n    tail_recur_pulse_start_step: int = int(os.environ.get("TAIL_RECUR_PULSE_START_STEP", 64))\n    tail_recur_pulse_end_step: int = int(os.environ.get("TAIL_RECUR_PULSE_END_STEP", 480))\n    beta1: float = float(os.environ.get("BETA1", 0.9))\n',
)
code = _replace_once(
    code,
    'def tail_recur_schedule(args: Hyperparameters, step: int, active_blocks: int) -> mx.array:\n    if active_blocks <= 0:\n        return mx.zeros((0,), dtype=mx.float32)\n    if args.tail_recur_ramp_end <= args.tail_recur_ramp_start:\n',
    'def tail_recur_schedule(args: Hyperparameters, step: int, active_blocks: int) -> mx.array:\n    if active_blocks <= 0:\n        return mx.zeros((0,), dtype=mx.float32)\n    if (\n        active_blocks > 1\n        and args.tail_recur_pulse_every > 0\n        and args.tail_recur_pulse_start_step <= step < args.tail_recur_pulse_end_step\n        and step % args.tail_recur_pulse_every == args.tail_recur_pulse_every - 1\n    ):\n        return mx.ones((active_blocks,), dtype=mx.float32)\n    if args.tail_recur_ramp_end <= args.tail_recur_ramp_start:\n',
)
code = _replace_once(
    code,
    '    log(f"tail_recur_staging:gap:{args.tail_recur_stage_gap} span:{args.tail_recur_stage_span}")\n    log("tail_ema:decay:{:.2f} tracked_float_kept:all tracked_proj_suffixes:all".format(PROJ_EMA_DECAY))\n',
    '    log(f"tail_recur_staging:gap:{args.tail_recur_stage_gap} span:{args.tail_recur_stage_span}")\n    log(f"tail_recur_pulse:every:{args.tail_recur_pulse_every} start_step:{args.tail_recur_pulse_start_step} end_step:{args.tail_recur_pulse_end_step}")\n    log("tail_ema:decay:{:.2f} tracked_float_kept:all tracked_proj_suffixes:all".format(PROJ_EMA_DECAY))\n',
)
globals()["__patched_source__"] = code
exec(compile(code, str(Path(__file__).resolve()), "exec"), globals(), globals())
