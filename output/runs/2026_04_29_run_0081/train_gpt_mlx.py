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
    '    tail_recur_min_gain: float = float(os.environ.get("TAIL_RECUR_MIN_GAIN", 0.35))\n    tail_recur_stage_gap: float = float(os.environ.get("TAIL_RECUR_STAGE_GAP", 0.16))\n',
    '    tail_recur_min_gain: float = float(os.environ.get("TAIL_RECUR_MIN_GAIN", 0.35))\n    tail_recur_exit_gain: float = float(os.environ.get("TAIL_RECUR_EXIT_GAIN", 1.06))\n    tail_recur_stage_gap: float = float(os.environ.get("TAIL_RECUR_STAGE_GAP", 0.16))\n',
)
code = _replace_once(
    code,
    '    if active_blocks == 1:\n        return mx.ones((1,), dtype=mx.float32)\n',
    '    if active_blocks == 1:\n        return mx.array((args.tail_recur_exit_gain,), dtype=mx.float32)\n',
)
code = _replace_once(
    code,
    '    gains[-1] = 1.0\n    return mx.array(gains, dtype=mx.float32)\ndef main() -> None:\n',
    '    gains[-1] = args.tail_recur_exit_gain\n    return mx.array(gains, dtype=mx.float32)\ndef tail_recur_eval_schedule(args: Hyperparameters, active_blocks: int) -> mx.array:\n    gains = np.ones((max(active_blocks, 0),), dtype=np.float32)\n    if active_blocks > 0:\n        gains[-1] = args.tail_recur_exit_gain\n    return mx.array(gains, dtype=mx.float32)\ndef main() -> None:\n',
)
code = _replace_once(
    code,
    '    tail_recur_eval_gains = mx.ones((args.tail_recur_blocks,), dtype=mx.float32)\n',
    '    tail_recur_eval_gains = tail_recur_eval_schedule(args, args.tail_recur_blocks)\n',
)
code = _replace_once(
    code,
    '    log(f"tail_recur_curriculum:min_gain:{args.tail_recur_min_gain} ramp_start:{args.tail_recur_ramp_start} ramp_end:{args.tail_recur_ramp_end}")\n',
    '    log(f"tail_recur_curriculum:min_gain:{args.tail_recur_min_gain} exit_gain:{args.tail_recur_exit_gain} ramp_start:{args.tail_recur_ramp_start} ramp_end:{args.tail_recur_ramp_end}")\n',
)
globals()["__patched_source__"] = code
exec(compile(code, str(Path(__file__).resolve()), "exec"), globals(), globals())
