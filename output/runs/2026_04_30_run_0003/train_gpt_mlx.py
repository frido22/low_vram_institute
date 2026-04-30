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
    '    tail_recur_min_gain: float = float(os.environ.get("TAIL_RECUR_MIN_GAIN", 0.35))\n    tail_recur_stage_gap: float = float(os.environ.get("TAIL_RECUR_STAGE_GAP", 0.16))\n',
    '    tail_recur_min_gain: float = float(os.environ.get("TAIL_RECUR_MIN_GAIN", 0.35))\n    tail_recur_eval_min_gain: float = float(os.environ.get("TAIL_RECUR_EVAL_MIN_GAIN", 0.86))\n    tail_recur_stage_gap: float = float(os.environ.get("TAIL_RECUR_STAGE_GAP", 0.16))\n',
)
code = _replace_once(
    code,
    'def tail_recur_schedule(args: Hyperparameters, step: int, active_blocks: int) -> mx.array:\n',
    'def tail_recur_eval_profile(args: Hyperparameters) -> mx.array:\n    gains = np.ones((args.tail_recur_blocks,), dtype=np.float32)\n    if args.tail_recur_blocks > 1:\n        gains[:-1] = np.linspace(args.tail_recur_eval_min_gain, 1.0, args.tail_recur_blocks, dtype=np.float32)[:-1]\n    return mx.array(gains, dtype=mx.float32)\ndef quant_aware_progress(args: Hyperparameters, step: int, elapsed_ms: float, max_wallclock_ms: float | None, reserved_final_ms: float) -> float:\n    if args.quant_aware_every <= 0:\n        return 0.0\n    if max_wallclock_ms is None:\n        start = max(args.iterations - args.quant_aware_iters, 0)\n        return min(max((step - start) / max(args.quant_aware_iters, 1), 0.0), 1.0)\n    start_ms = max(max_wallclock_ms - reserved_final_ms - 1000.0 * args.quant_aware_train_seconds, 0.0)\n    return min(max((elapsed_ms - start_ms) / max(1000.0 * args.quant_aware_train_seconds, 1.0), 0.0), 1.0)\ndef tail_recur_schedule(args: Hyperparameters, step: int, active_blocks: int) -> mx.array:\n',
)
code = _replace_once(
    code,
    '    tail_recur_eval_gains = mx.ones((args.tail_recur_blocks,), dtype=mx.float32)\n',
    '    tail_recur_eval_gains = tail_recur_eval_profile(args)\n',
)
code = _replace_once(
    code,
    '    log(f"tail_recur_curriculum:min_gain:{args.tail_recur_min_gain} ramp_start:{args.tail_recur_ramp_start} ramp_end:{args.tail_recur_ramp_end}")\n',
    '    log(f"tail_recur_curriculum:min_gain:{args.tail_recur_min_gain} eval_min_gain:{args.tail_recur_eval_min_gain} ramp_start:{args.tail_recur_ramp_start} ramp_end:{args.tail_recur_ramp_end}")\n',
)
code = _replace_once(
    code,
    '        tail_recur_gains = tail_recur_schedule(args, step, args.tail_recur_blocks)\n        if args.use_single_microbatch_path:\n',
    '        tail_recur_gains = tail_recur_schedule(args, step, args.tail_recur_blocks)\n        tail_bridge = quant_aware_progress(args, step, approx_train_time_ms, max_wallclock_ms, reserved_final_ms)\n        if tail_bridge > 0.0:\n            tail_recur_gains = tail_recur_gains + (tail_recur_eval_gains - tail_recur_gains) * tail_bridge\n        if args.use_single_microbatch_path:\n',
)
globals()["__patched_source__"] = code
exec(compile(code, str(Path(__file__).resolve()), "exec"), globals(), globals())
