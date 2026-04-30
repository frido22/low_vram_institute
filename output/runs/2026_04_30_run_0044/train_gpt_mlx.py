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
    '    tail_recur_min_gain: float = float(os.environ.get("TAIL_RECUR_MIN_GAIN", 0.35))\n',
    '    tail_recur_min_gain: float = float(os.environ.get("TAIL_RECUR_MIN_GAIN", 0.35))\n    tail_recur_final_min_gain: float = float(os.environ.get("TAIL_RECUR_FINAL_MIN_GAIN", 0.86))\n',
)
code = _replace_once(
    code,
    '''def tail_recur_schedule(args: Hyperparameters, step: int, active_blocks: int) -> mx.array:\n    if active_blocks <= 0:\n        return mx.zeros((0,), dtype=mx.float32)\n    if args.tail_recur_ramp_end <= args.tail_recur_ramp_start:\n        progress = 1.0 if step > 0 else 0.0\n    else:\n        progress = step / max(args.iterations, 1)\n        progress = min(max((progress - args.tail_recur_ramp_start) / (args.tail_recur_ramp_end - args.tail_recur_ramp_start), 0.0), 1.0)\n    if active_blocks == 1:\n        return mx.ones((1,), dtype=mx.float32)\n    gains = np.ones((active_blocks,), dtype=np.float32)\n    for idx in range(active_blocks - 1):\n        stage_start = idx * args.tail_recur_stage_gap\n        stage_span = max(args.tail_recur_stage_span, 1e-6)\n        stage_progress = min(max((progress - stage_start) / stage_span, 0.0), 1.0)\n        gains[idx] = args.tail_recur_min_gain + (1.0 - args.tail_recur_min_gain) * stage_progress\n    gains[-1] = 1.0\n    return mx.array(gains, dtype=mx.float32)\n''',
    '''def tail_recur_gain_profile(active_blocks: int, min_gain: float) -> np.ndarray:\n    if active_blocks <= 0:\n        return np.zeros((0,), dtype=np.float32)\n    if active_blocks == 1:\n        return np.ones((1,), dtype=np.float32)\n    return np.linspace(min_gain, 1.0, active_blocks, dtype=np.float32)\ndef tail_recur_schedule(args: Hyperparameters, step: int, active_blocks: int) -> mx.array:\n    if active_blocks <= 0:\n        return mx.zeros((0,), dtype=mx.float32)\n    if args.tail_recur_ramp_end <= args.tail_recur_ramp_start:\n        progress = 1.0 if step > 0 else 0.0\n    else:\n        progress = step / max(args.iterations, 1)\n        progress = min(max((progress - args.tail_recur_ramp_start) / (args.tail_recur_ramp_end - args.tail_recur_ramp_start), 0.0), 1.0)\n    target_gains = tail_recur_gain_profile(active_blocks, args.tail_recur_final_min_gain)\n    gains = target_gains.copy()\n    for idx in range(active_blocks - 1):\n        stage_start = idx * args.tail_recur_stage_gap\n        stage_span = max(args.tail_recur_stage_span, 1e-6)\n        stage_progress = min(max((progress - stage_start) / stage_span, 0.0), 1.0)\n        gains[idx] = args.tail_recur_min_gain + (target_gains[idx] - args.tail_recur_min_gain) * stage_progress\n    return mx.array(gains, dtype=mx.float32)\n''',
)
code = _replace_once(
    code,
    '    tail_recur_eval_gains = mx.ones((args.tail_recur_blocks,), dtype=mx.float32)\n',
    '    tail_recur_eval_gains = mx.array(tail_recur_gain_profile(args.tail_recur_blocks, args.tail_recur_final_min_gain), dtype=mx.float32)\n',
)
code = _replace_once(
    code,
    '    log(f"tail_recur_curriculum:min_gain:{args.tail_recur_min_gain} ramp_start:{args.tail_recur_ramp_start} ramp_end:{args.tail_recur_ramp_end}")\n',
    '    log(f"tail_recur_curriculum:min_gain:{args.tail_recur_min_gain} final_min_gain:{args.tail_recur_final_min_gain} ramp_start:{args.tail_recur_ramp_start} ramp_end:{args.tail_recur_ramp_end}")\n',
)
globals()["__patched_source__"] = code
exec(compile(code, str(Path(__file__).resolve()), "exec"), globals(), globals())
