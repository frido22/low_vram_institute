#!/usr/bin/env python3
from __future__ import annotations
import importlib.util
import os
from pathlib import Path

TAIL_POSITION_WEIGHTED_WRAPPER = True
MAX_WALLCLOCK_SECONDS_MARKER = "MAX_WALLCLOCK_SECONDS"
FINAL_EXACT_MARKER = "final_int8_zlib_roundtrip_exact"


def _looks_like_wrapper(path: Path) -> bool:
    try:
        return "TAIL_POSITION_WEIGHTED_WRAPPER" in path.read_text(encoding="utf-8", errors="ignore")[:8192]
    except OSError:
        return False


def _find_base_script() -> Path:
    here = Path(__file__).resolve()
    roots = []
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
                root / "state" / "best_script.py.bak",
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
spec = importlib.util.spec_from_file_location("tail_focus_base_script", BASE_SCRIPT)
if spec is None or spec.loader is None:
    raise ImportError(f"Unable to load base script from {BASE_SCRIPT}")
base = importlib.util.module_from_spec(spec)
spec.loader.exec_module(base)


class Hyperparameters(base.Hyperparameters):
    train_tail_focus_base_weight: float = float(os.environ.get("TRAIN_TAIL_FOCUS_BASE_WEIGHT", 0.35))
    train_tail_focus_tokens: int = int(os.environ.get("TRAIN_TAIL_FOCUS_TOKENS", os.environ.get("EVAL_STRIDE", 64)))


class TailFocusGPT(base.GPT):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        hp = base.Hyperparameters
        self.train_tail_focus_base_weight = min(max(float(hp.train_tail_focus_base_weight), 0.0), 1.0)
        self.train_tail_focus_tokens = max(int(hp.train_tail_focus_tokens), 0)

    def masked_loss(self, input_ids: base.mx.array, target_ids: base.mx.array, loss_mask: base.mx.array) -> base.mx.array:
        x = self(input_ids).reshape(-1, self.tok_emb.weight.shape[1]); y = target_ids.reshape(-1); prev_ids = input_ids.reshape(-1)
        mask = loss_mask.reshape(-1).astype(base.mx.float32)
        denom = base.mx.maximum(base.mx.sum(mask), base.mx.array(1.0, dtype=base.mx.float32))
        if self.logit_chunk_tokens <= 0 or x.shape[0] <= self.logit_chunk_tokens:
            logits = self.project_logits(x, prev_ids)
            logits_f = logits.astype(base.mx.float32)
            token_loss = base.mx.logsumexp(logits_f, axis=-1) - base.mx.take_along_axis(logits_f, y[:, None], axis=-1).reshape(-1)
            return base.mx.sum(token_loss.astype(base.mx.float32) * mask) / denom
        loss_sum = base.mx.array(0.0, dtype=base.mx.float32)
        n = int(x.shape[0])
        for s in range(0, n, self.logit_chunk_tokens):
            e = min(s + self.logit_chunk_tokens, n)
            logits = self.project_logits(x[s:e], prev_ids[s:e])
            logits_f = logits.astype(base.mx.float32)
            token_loss = base.mx.logsumexp(logits_f, axis=-1) - base.mx.take_along_axis(logits_f, y[s:e, None], axis=-1).reshape(-1)
            loss_sum = loss_sum + base.mx.sum(token_loss.astype(base.mx.float32) * mask[s:e])
        return loss_sum / denom

    def train_loss(self, input_ids: base.mx.array, target_ids: base.mx.array) -> base.mx.array:
        if self.train_tail_focus_base_weight >= 1.0 or self.train_tail_focus_tokens <= 0:
            return super().loss(input_ids, target_ids)
        tail_tokens = min(self.train_tail_focus_tokens, target_ids.shape[1])
        row = self.train_tail_focus_base_weight + (1.0 - self.train_tail_focus_base_weight) * (
            base.mx.arange(target_ids.shape[1]) >= target_ids.shape[1] - tail_tokens
        ).astype(base.mx.float32)
        return self.masked_loss(input_ids, target_ids, row[None, :] + base.mx.zeros(target_ids.shape, dtype=base.mx.float32))


_orig_value_and_grad = base.nn.value_and_grad


def _value_and_grad(module, fn):
    if isinstance(module, TailFocusGPT):
        return _orig_value_and_grad(module, lambda x, y: module.train_loss(x, y))
    return _orig_value_and_grad(module, fn)


base.Hyperparameters = Hyperparameters
base.GPT = TailFocusGPT
base.nn.value_and_grad = _value_and_grad


if __name__ == "__main__":
    base.main()
