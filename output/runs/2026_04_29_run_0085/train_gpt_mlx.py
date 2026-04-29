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
    '    tail_recur_stage_span: float = float(os.environ.get("TAIL_RECUR_STAGE_SPAN", 0.12))\n    beta1: float = float(os.environ.get("BETA1", 0.9))\n',
    '    tail_recur_stage_span: float = float(os.environ.get("TAIL_RECUR_STAGE_SPAN", 0.12))\n    tail_recur_quant_aware_blend: float = float(os.environ.get("TAIL_RECUR_QUANT_AWARE_BLEND", 0.55))\n    beta1: float = float(os.environ.get("BETA1", 0.9))\n',
)
code = _replace_once(
    code,
    'CONTROL_TENSOR_NAME_PATTERNS = tuple(pattern for pattern in os.environ.get("CONTROL_TENSOR_NAME_PATTERNS", "attn_scale,attn_scales,mlp_scale,mlp_scales,resid_mix,resid_mixes,q_gain,skip_weight,skip_weights,tail_recur_gates,tail_carry_gates").split(",") if pattern)\n',
    'CONTROL_TENSOR_NAME_PATTERNS = tuple(pattern for pattern in os.environ.get("CONTROL_TENSOR_NAME_PATTERNS", "attn_scale,attn_scales,mlp_scale,mlp_scales,resid_mix,resid_mixes,q_gain,skip_weight,skip_weights,tail_recur_gates,tail_carry_gates,logit_bias,logit_gain,bigram_scale").split(",") if pattern)\n',
)
code = _replace_once(
    code,
    '    log(f"tail_recur_staging:gap:{args.tail_recur_stage_gap} span:{args.tail_recur_stage_span}")\n    log("tail_ema:decay:{:.2f} tracked_float_kept:all tracked_proj_suffixes:all".format(PROJ_EMA_DECAY))\n',
    '    log(f"tail_recur_staging:gap:{args.tail_recur_stage_gap} span:{args.tail_recur_stage_span}")\n    log(f"tail_recur_endgame:quant_aware_blend:{args.tail_recur_quant_aware_blend}")\n    log("tail_ema:decay:{:.2f} tracked_float_kept:all tracked_proj_suffixes:all".format(PROJ_EMA_DECAY))\n',
)
code = _replace_once(
    code,
    '        tail_recur_gains = tail_recur_schedule(args, step, args.tail_recur_blocks)\n        if args.use_single_microbatch_path:\n',
    '        tail_recur_gains = tail_recur_schedule(args, step, args.tail_recur_blocks)\n        if quant_aware_active and args.tail_recur_quant_aware_blend > 0.0:\n            tail_recur_gains = tail_recur_gains + (tail_recur_eval_gains - tail_recur_gains) * args.tail_recur_quant_aware_blend\n        if args.use_single_microbatch_path:\n',
)
globals()["__patched_source__"] = code
exec(compile(code, str(Path(__file__).resolve()), "exec"), globals(), globals())
