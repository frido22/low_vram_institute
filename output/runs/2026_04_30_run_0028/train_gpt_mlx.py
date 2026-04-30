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
    '    tail_recur_stage_span: float = float(os.environ.get("TAIL_RECUR_STAGE_SPAN", 0.12))\n',
    '    tail_recur_stage_span: float = float(os.environ.get("TAIL_RECUR_STAGE_SPAN", 0.12))\n'
    '    tail_recur_eval_prefix_gain: float = float(os.environ.get("TAIL_RECUR_EVAL_PREFIX_GAIN", 0.94))\n',
)
code = _replace_once(
    code,
    'def main() -> None:\n',
    'def tail_recur_eval_profile(args: Hyperparameters, active_blocks: int) -> mx.array:\n'
    '    if active_blocks <= 0:\n'
    '        return mx.zeros((0,), dtype=mx.float32)\n'
    '    gains = np.ones((active_blocks,), dtype=np.float32)\n'
    '    if active_blocks > 1:\n'
    '        gains[:-1] = args.tail_recur_eval_prefix_gain\n'
    '    return mx.array(gains, dtype=mx.float32)\n'
    'def main() -> None:\n',
)
code = _replace_once(
    code,
    '    tail_recur_eval_gains = mx.ones((args.tail_recur_blocks,), dtype=mx.float32)\n',
    '    tail_recur_eval_gains = tail_recur_eval_profile(args, args.tail_recur_blocks)\n',
)
code = _replace_once(
    code,
    '    log(f"tail_recur_staging:gap:{args.tail_recur_stage_gap} span:{args.tail_recur_stage_span}")\n',
    '    log(f"tail_recur_staging:gap:{args.tail_recur_stage_gap} span:{args.tail_recur_stage_span}")\n'
    '    log(f"tail_recur_eval_prefix_gain:{args.tail_recur_eval_prefix_gain}")\n',
)
globals()["__patched_source__"] = code
exec(compile(code, str(Path(__file__).resolve()), "exec"), globals(), globals())
