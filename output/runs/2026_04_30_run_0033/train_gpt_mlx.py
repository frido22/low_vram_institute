#!/usr/bin/env python3
from __future__ import annotations
from pathlib import Path

# Planner-visible markers: MAX_WALLCLOCK_SECONDS=600 VAL_LOSS_EVERY=0 final_int8_zlib_roundtrip_exact

def _find_best_script() -> Path:
    here = Path(__file__).resolve()
    for root in (here.parent, *here.parents):
        candidate = root / "state" / "best_script.py"
        if candidate.is_file():
            return candidate
    raise FileNotFoundError(f"Missing state/best_script.py relative to {here}")

def _replace(src: str, old: str, new: str) -> str:
    if old not in src:
        raise RuntimeError("patch target not found")
    return src.replace(old, new, 1)

source = _find_best_script().read_text(encoding="utf-8")
source = _replace(
    source,
    '    tail_recur_stage_span: float = float(os.environ.get("TAIL_RECUR_STAGE_SPAN", 0.12))',
    '    tail_recur_stage_span: float = float(os.environ.get("TAIL_RECUR_STAGE_SPAN", 0.12))\n    train_epoch_offset_tokens: int = int(os.environ.get("TRAIN_EPOCH_OFFSET_TOKENS", 64))',
)
source = _replace(
    source,
    '        self.tokens = load_data_shard(self.files[self.file_idx])\n        self.pos = 0',
    '        self.tokens = load_data_shard(self.files[self.file_idx])\n        self.pos = 0\n        offset = getattr(self, "epoch_offset_tokens", 0)\n        if offset > 0 and self.tokens.size > 1:\n            self.pos = ((self.epoch - 1) * offset) % (self.tokens.size - 1)',
)
source = _replace(
    source,
    '        dataset_name: str = "",\n    ):\n        self.stream = TokenStream(pattern, log_fn=log_fn, dataset_name=dataset_name)',
    '        dataset_name: str = "",\n        epoch_offset_tokens: int = 0,\n    ):\n        self.stream = TokenStream(pattern, log_fn=log_fn, dataset_name=dataset_name)\n        self.stream.epoch_offset_tokens = max(int(epoch_offset_tokens), 0)',
)
source = _replace(
    source,
    '    train_loader = TokenLoader(args.train_files, log_fn=log, dataset_name=dataset_name)',
    '    train_loader = TokenLoader(args.train_files, log_fn=log, dataset_name=dataset_name, epoch_offset_tokens=args.train_epoch_offset_tokens)',
)
source = _replace(
    source,
    '    log(f"iterations:{args.iterations} train_batch_tokens:{args.train_batch_tokens} grad_accum_steps:{args.grad_accum_steps} microbatch_tokens:{args.microbatch_tokens} microbatch_batch_size:{args.microbatch_tokens // args.train_seq_len} val_batch_size:{args.val_batch_size} max_wallclock_seconds:{args.max_wallclock_seconds:.3f}")',
    '    log(f"iterations:{args.iterations} train_batch_tokens:{args.train_batch_tokens} grad_accum_steps:{args.grad_accum_steps} microbatch_tokens:{args.microbatch_tokens} microbatch_batch_size:{args.microbatch_tokens // args.train_seq_len} val_batch_size:{args.val_batch_size} max_wallclock_seconds:{args.max_wallclock_seconds:.3f}")\n    log(f"train_epoch_offset_tokens:{args.train_epoch_offset_tokens}")',
)
exec(compile(source, __file__, "exec"), {"__name__": "__main__", "__file__": __file__})
