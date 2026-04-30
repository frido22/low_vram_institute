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
    'CONTROL_TENSOR_NAME_PATTERNS = tuple(pattern for pattern in os.environ.get("CONTROL_TENSOR_NAME_PATTERNS", "attn_scale,attn_scales,mlp_scale,mlp_scales,resid_mix,resid_mixes,q_gain,skip_weight,skip_weights,tail_recur_gates,tail_carry_gates").split(",") if pattern)\n',
    'CONTROL_TENSOR_NAME_PATTERNS = tuple(pattern for pattern in os.environ.get("CONTROL_TENSOR_NAME_PATTERNS", "attn_scale,attn_scales,mlp_scale,mlp_scales,resid_mix,resid_mixes,q_gain,skip_weight,skip_weights,tail_recur_gates,tail_carry_gates,tail_recur_gain").split(",") if pattern)\n',
)
code = _replace_once(
    code,
    '        self.tail_recur_gates = mx.zeros((tail_recur_span, dim), dtype=mx.float32) if tail_recur_span > 0 else None; self.tail_carry_gates = mx.zeros((tail_recur_span, dim), dtype=mx.float32) if tail_recur_span > 0 else None\n',
    '        self.tail_recur_gates = mx.zeros((tail_recur_span, dim), dtype=mx.float32) if tail_recur_span > 0 else None; self.tail_carry_gates = mx.zeros((tail_recur_span, dim), dtype=mx.float32) if tail_recur_span > 0 else None; self.tail_recur_gain_bias = mx.zeros((tail_recur_span,), dtype=mx.float32) if tail_recur_span > 0 else None\n',
)
code = _replace_once(
    code,
    '                recur_gain = 1.0 if tail_recur_gains is None else tail_recur_gains[recur_idx].astype(x.dtype)\n                recur_x = x + recur_gain * mx.tanh(self.tail_carry_gates[recur_idx]).astype(x.dtype)[None, None, :] * (tail_anchor - x); x = recur_x + recur_gain * mx.tanh(self.tail_recur_gates[recur_idx]).astype(x.dtype)[None, None, :] * (self.blocks[block_idx](recur_x, x0) - recur_x)\n',
    '                recur_gain = 1.0 if tail_recur_gains is None else tail_recur_gains[recur_idx].astype(x.dtype)\n                recur_gain = recur_gain * (1.0 + 0.25 * mx.tanh(self.tail_recur_gain_bias[recur_idx]).astype(x.dtype))\n                recur_x = x + recur_gain * mx.tanh(self.tail_carry_gates[recur_idx]).astype(x.dtype)[None, None, :] * (tail_anchor - x); x = recur_x + recur_gain * mx.tanh(self.tail_recur_gates[recur_idx]).astype(x.dtype)[None, None, :] * (self.blocks[block_idx](recur_x, x0) - recur_x)\n',
)
code = _replace_once(
    code,
    '    log("tail_recur_order:reverse"); log("tail_recur_carry:decoder_output_anchor")\n    log(f"tail_recur_curriculum:min_gain:{args.tail_recur_min_gain} ramp_start:{args.tail_recur_ramp_start} ramp_end:{args.tail_recur_ramp_end}")\n',
    '    log("tail_recur_order:reverse"); log("tail_recur_carry:decoder_output_anchor")\n    log("tail_recur_gain:learned_block_scalar span:0.25")\n    log(f"tail_recur_curriculum:min_gain:{args.tail_recur_min_gain} ramp_start:{args.tail_recur_ramp_start} ramp_end:{args.tail_recur_ramp_end}")\n',
)
globals()["__patched_source__"] = code
exec(compile(code, str(Path(__file__).resolve()), "exec"), globals(), globals())
