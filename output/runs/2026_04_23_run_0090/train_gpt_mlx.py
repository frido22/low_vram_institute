#!/usr/bin/env python3
from __future__ import annotations
import importlib.util
import os
from pathlib import Path

FINAL_BLOCK_TAIL_RECURRENCE_WRAPPER = True
MAX_WALLCLOCK_SECONDS_MARKER = "MAX_WALLCLOCK_SECONDS"
FINAL_EXACT_MARKER = "final_int8_zlib_roundtrip_exact"


def _looks_like_wrapper(path: Path) -> bool:
    try:
        head = path.read_text(encoding="utf-8", errors="ignore")[:8192]
    except OSError:
        return False
    return "FINAL_BLOCK_TAIL_RECURRENCE_WRAPPER" in head


def _find_base_script() -> Path:
    here = Path(__file__).resolve()
    roots: list[Path] = []
    for root in (here.parent, *here.parents, Path.cwd(), *Path.cwd().parents):
        if root not in roots:
            roots.append(root)
    candidates: list[Path] = []
    env_base = os.environ.get("LOW_VRAM_BASE_SCRIPT")
    if env_base:
        candidates.append(Path(env_base))
    for root in roots:
        candidates.extend(
            [
                root / "state" / "best_script.py",
                root / "output" / "runs" / "2026_04_23_run_0031" / "train_gpt_mlx.py",
                root / "output" / "runs" / "2026_04_23_run_0086" / "train_gpt_mlx.py",
            ]
        )
    for candidate in candidates:
        try:
            resolved = candidate.resolve()
        except OSError:
            continue
        if resolved != here and candidate.is_file() and not _looks_like_wrapper(candidate):
            return candidate
    raise FileNotFoundError("Could not locate a non-wrapper current-best train_gpt_mlx.py")


BASE_SCRIPT = _find_base_script()
spec = importlib.util.spec_from_file_location("final_block_tail_base", BASE_SCRIPT)
if spec is None or spec.loader is None:
    raise ImportError(f"Unable to load base script from {BASE_SCRIPT}")
base = importlib.util.module_from_spec(spec)
spec.loader.exec_module(base)

_EXTRA_CONTROL_NAMES = ("tail_final_recur_gate", "tail_final_carry_gate")
base.CONTROL_TENSOR_NAME_PATTERNS = tuple(dict.fromkeys((*base.CONTROL_TENSOR_NAME_PATTERNS, *_EXTRA_CONTROL_NAMES)))
base.INT8_KEEP_FLOAT_FP32_NAME_PATTERNS = tuple(dict.fromkeys((*base.INT8_KEEP_FLOAT_FP32_NAME_PATTERNS, *_EXTRA_CONTROL_NAMES)))


class FinalBlockTailGPT(base.GPT):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        dim = int(self.tok_emb.weight.shape[1])
        if self.tail_recur_gates is None:
            self.tail_final_recur_gate = None
            self.tail_final_carry_gate = None
        else:
            init = float(os.environ.get("TAIL_FINAL_RECUR_GATE_INIT", "0.02"))
            self.tail_final_recur_gate = base.mx.ones((dim,), dtype=base.mx.float32) * init
            self.tail_final_carry_gate = base.mx.zeros((dim,), dtype=base.mx.float32)

    def __call__(self, input_ids: base.mx.array) -> base.mx.array:
        x = base.rms_norm(self.tok_emb(input_ids).astype(base.COMPUTE_DTYPE))
        x0 = x
        skips: list[base.mx.array] = []
        for i in range(self.num_encoder_layers):
            x = self.blocks[i](x, x0)
            skips.append(x)
        for i in range(self.num_decoder_layers):
            skip_idx = i - self.decoder_skip_start
            if 0 <= skip_idx < int(self.skip_weights.shape[0]) and skips:
                x = x + self.skip_weights[skip_idx].astype(x.dtype)[None, None, :] * skips.pop()
            x = self.blocks[self.num_encoder_layers + i](x, x0)
        if self.tail_recur_gates is not None:
            tail_anchor = x
            for block_idx in range(len(self.blocks) - 1, self.tail_recur_start - 1, -1):
                recur_idx = block_idx - self.tail_recur_start
                recur_x = x + base.mx.tanh(self.tail_carry_gates[recur_idx]).astype(x.dtype)[None, None, :] * (tail_anchor - x)
                x = recur_x + base.mx.tanh(self.tail_recur_gates[recur_idx]).astype(x.dtype)[None, None, :] * (self.blocks[block_idx](recur_x, x0) - recur_x)
            recur_x = x + base.mx.tanh(self.tail_final_carry_gate).astype(x.dtype)[None, None, :] * (tail_anchor - x)
            x = recur_x + base.mx.tanh(self.tail_final_recur_gate).astype(x.dtype)[None, None, :] * (self.blocks[-1](recur_x, x0) - recur_x)
        return self.final_norm(x)


base.GPT = FinalBlockTailGPT

if __name__ == "__main__":
    base.main()
