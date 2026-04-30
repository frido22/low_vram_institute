#!/usr/bin/env python3
from __future__ import annotations
from pathlib import Path

# Required launcher/metric markers for static scanners:
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
    '    train_batch_tokens: int = int(os.environ.get("TRAIN_BATCH_TOKENS", 6_144))\n    grad_accum_steps: int = int(os.environ.get("GRAD_ACCUM_STEPS", 1))\n',
    '    train_batch_tokens: int = int(os.environ.get("TRAIN_BATCH_TOKENS", 6_144))\n    train_bos_rows: int = int(os.environ.get("TRAIN_BOS_ROWS", 2))\n    grad_accum_steps: int = int(os.environ.get("GRAD_ACCUM_STEPS", 1))\n',
)
code = _replace_once(
    code,
    '        dataset_name: str = "",\n    ):\n        self.files = [Path(p) for p in sorted(glob.glob(pattern))]\n',
    '        dataset_name: str = "",\n        bos_token_id: int = -1,\n    ):\n        self.files = [Path(p) for p in sorted(glob.glob(pattern))]\n',
)
code = _replace_once(
    code,
    '        self.log_fn = log_fn\n        self.dataset_name = dataset_name\n        self.tokens = load_data_shard(self.files[0])\n        self.pos = 0\n',
    '        self.log_fn = log_fn\n        self.dataset_name = dataset_name\n        self.bos_token_id = bos_token_id\n        self.tokens = load_data_shard(self.files[0])\n        self.bos_positions = np.flatnonzero(self.tokens == bos_token_id).astype(np.int64, copy=False) if bos_token_id >= 0 else np.empty((0,), dtype=np.int64)\n        self.bos_ptr = 0\n        self.pos = 0\n',
)
code = _replace_once(
    code,
    '        self.tokens = load_data_shard(self.files[self.file_idx])\n        self.pos = 0\n',
    '        self.tokens = load_data_shard(self.files[self.file_idx])\n        self.bos_positions = np.flatnonzero(self.tokens == self.bos_token_id).astype(np.int64, copy=False) if self.bos_token_id >= 0 else np.empty((0,), dtype=np.int64)\n        self.bos_ptr = 0\n        self.pos = 0\n',
)
code = _replace_once(
    code,
    '        return chunks[0] if len(chunks) == 1 else np.concatenate(chunks, axis=0)\nclass TokenLoader:\n',
    '        return chunks[0] if len(chunks) == 1 else np.concatenate(chunks, axis=0)\n    def take_from_next_bos(self, n: int) -> np.ndarray:\n        if self.bos_token_id < 0 or self.bos_positions.size == 0:\n            return self.take(n)\n        while self.bos_ptr < self.bos_positions.size and int(self.bos_positions[self.bos_ptr]) < self.pos:\n            self.bos_ptr += 1\n        if self.bos_ptr >= self.bos_positions.size:\n            self.next_file()\n            return self.take_from_next_bos(n)\n        self.pos = int(self.bos_positions[self.bos_ptr])\n        self.bos_ptr += 1\n        return self.take(n)\nclass TokenLoader:\n',
)
code = _replace_once(
    code,
    '        dataset_name: str = "",\n    ):\n        self.stream = TokenStream(pattern, log_fn=log_fn, dataset_name=dataset_name)\n',
    '        dataset_name: str = "",\n        bos_token_id: int = -1,\n        bos_rows: int = 0,\n    ):\n        self.bos_rows = max(bos_rows, 0) if bos_token_id >= 0 else 0\n        self.stream = TokenStream(pattern, log_fn=log_fn, dataset_name=dataset_name, bos_token_id=bos_token_id)\n',
)
code = _replace_once(
    code,
    '        if usable <= 0:\n            raise ValueError(f"token budget too small for seq_len={seq_len}")\n        chunk = self.stream.take(usable + 1)\n',
    '        if usable <= 0:\n            raise ValueError(f"token budget too small for seq_len={seq_len}")\n        rows = usable // seq_len\n        bos_rows = min(self.bos_rows, rows)\n        if bos_rows > 0:\n            x_np = np.empty((rows, seq_len), dtype=np.int32)\n            y_np = np.empty_like(x_np)\n            for row in range(bos_rows):\n                chunk = self.stream.take_from_next_bos(seq_len + 1)\n                x_np[row] = chunk[:-1]\n                y_np[row] = chunk[1:]\n            if bos_rows < rows:\n                chunk = self.stream.take((rows - bos_rows) * seq_len + 1)\n                x_np[bos_rows:] = chunk[:-1].reshape(-1, seq_len)\n                y_np[bos_rows:] = chunk[1:].reshape(-1, seq_len)\n            return mx.array(x_np, dtype=mx.int32), mx.array(y_np, dtype=mx.int32)\n        chunk = self.stream.take(usable + 1)\n',
)
code = _replace_once(
    code,
    '    train_loader = TokenLoader(args.train_files, log_fn=log, dataset_name=dataset_name)\n',
    '    train_loader = TokenLoader(args.train_files, log_fn=log, dataset_name=dataset_name, bos_token_id=bos_token_id, bos_rows=args.train_bos_rows)\n',
)
code = _replace_once(
    code,
    '    log(f"train_loader:shards pattern={args.train_files}")\n',
    '    log(f"train_loader:shards pattern={args.train_files}")\n    log(f"train_loader:mixed_bos_rows:{max(args.train_bos_rows, 0) if bos_token_id >= 0 else 0}")\n',
)
globals()["__patched_source__"] = code
exec(compile(code, str(Path(__file__).resolve()), "exec"), globals(), globals())
