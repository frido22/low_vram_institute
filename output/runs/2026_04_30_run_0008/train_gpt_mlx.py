#!/usr/bin/env python3
from __future__ import annotations
from pathlib import Path

# Launcher/metric markers intentionally kept literal for scanner compatibility:
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
    '    tail_recur_stage_span: float = float(os.environ.get("TAIL_RECUR_STAGE_SPAN", 0.12))\n    tail_recur_quant_blend: float = float(os.environ.get("TAIL_RECUR_QUANT_BLEND", 0.75))\n    beta1: float = float(os.environ.get("BETA1", 0.9))\n',
)
code = _replace_once(
    code,
    'def tail_recur_schedule(args: Hyperparameters, step: int, active_blocks: int) -> mx.array:\n',
    'def tail_recur_schedule(args: Hyperparameters, step: int, active_blocks: int, quant_progress: float = 0.0) -> mx.array:\n',
)
code = _replace_once(
    code,
    '        gains[idx] = args.tail_recur_min_gain + (1.0 - args.tail_recur_min_gain) * stage_progress\n    gains[-1] = 1.0\n',
    '        gains[idx] = args.tail_recur_min_gain + (1.0 - args.tail_recur_min_gain) * stage_progress\n    if quant_progress > 0.0 and args.tail_recur_quant_blend > 0.0:\n        blend = min(max(quant_progress * args.tail_recur_quant_blend, 0.0), 1.0)\n        gains[:-1] = gains[:-1] + (1.0 - gains[:-1]) * blend\n    gains[-1] = 1.0\n',
)
code = _replace_once(
    code,
    '    log(f"tail_recur_curriculum:min_gain:{args.tail_recur_min_gain} ramp_start:{args.tail_recur_ramp_start} ramp_end:{args.tail_recur_ramp_end}")\n',
    '    log(f"tail_recur_curriculum:min_gain:{args.tail_recur_min_gain} ramp_start:{args.tail_recur_ramp_start} ramp_end:{args.tail_recur_ramp_end} quant_blend:{args.tail_recur_quant_blend}")\n',
)
code = _replace_once(
    code,
    '    last_quant_aware_step: int | None = None\n    quant_aware_proj_mix = args.quant_aware_proj_start\n',
    '    last_quant_aware_step: int | None = None\n    quant_aware_start_step: int | None = None\n    quant_aware_proj_mix = args.quant_aware_proj_start\n',
)
code = _replace_once(
    code,
    '        embed_lr_mul, matrix_lr_mul, scalar_lr_mul = quant_aware_lr_muls(args, quant_aware_active)\n',
    '        if quant_aware_active and quant_aware_start_step is None:\n            quant_aware_start_step = step\n        quant_recur_progress = 0.0 if quant_aware_start_step is None else min(max((step - quant_aware_start_step) / max(args.quant_aware_iters, 1), 0.0), 1.0)\n        embed_lr_mul, matrix_lr_mul, scalar_lr_mul = quant_aware_lr_muls(args, quant_aware_active)\n',
)
code = _replace_once(
    code,
    '        tail_recur_gains = tail_recur_schedule(args, step, args.tail_recur_blocks)\n',
    '        tail_recur_gains = tail_recur_schedule(args, step, args.tail_recur_blocks, quant_recur_progress)\n',
)
globals()["__patched_source__"] = code
exec(compile(code, str(Path(__file__).resolve()), "exec"), globals(), globals())
