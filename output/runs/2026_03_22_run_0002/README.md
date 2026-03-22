# Train Short 512, Eval Long 1024

**Score:** 2.323567 val_bpb
**Hardware:** Apple Silicon Mac mini M4 16GB (600s wallclock cap; step count depends on the script)
**Runtime:** 184s

## Approach

The Mac mini baseline is dominated by severe undertraining: about 15 optimizer steps in 600s is too few for a 9x512 model to realize its capacity. The most plausible high-leverage move is to cut training attention cost without giving up the stronger final metric path. This patch decouples training and evaluation sequence lengths, defaults training to 512 tokens for faster updates, and preserves 1024-token doc-isolated sliding evaluation at the end. That keeps the current best evaluation trick intact while buying materially more gradient steps under the same wallclock.

## Changes

```diff
--- a/train_gpt_mlx.py
+++ b/train_gpt_mlx.py
@@ -31,8 +31,8 @@
 # Default Simple Baseline run:
 # - 9 transformer blocks at width 512
 # - 8 attention heads with 4 KV heads (GQA) and 2x MLP expansion
-# - vocab size 1024, sequence length 1024, tied embeddings
-# - 524,288 train tokens per step for 20,000 iterations with a ~10 minute cap
+# - vocab size 1024, tied embeddings
+# - train shorter sequences on Mac for more updates, but keep long-context eval
 class Hyperparameters:
     # Data / tokenizer.
     data_path: str = os.environ.get("DATA_PATH", "./data/datasets/fineweb10B_sp1024")
@@ -47,7 +47,8 @@
     train_log_every: int = int(os.environ.get("TRAIN_LOG_EVERY", 25))
     train_batch_tokens: int = int(os.environ.get("TRAIN_BATCH_TOKENS", 8_192))
     grad_accum_steps: int = int(os.environ.get("GRAD_ACCUM_STEPS", 1))
-    train_seq_len: int = int(os.environ.get("TRAIN_SEQ_LEN", os.environ.get("TRAIN_MAX_SEQ_LEN", 1024)))
+    train_seq_len: int = int(os.environ.get("TRAIN_SEQ_LEN", 512))
+    eval_seq_len: int = int(os.environ.get("EVAL_SEQ_LEN", os.environ.get("TRAIN_MAX_SEQ_LEN", 1024)))
     # Chunk each logical MLX microbatch into smaller sub-batches to reduce peak
     # memory pressure without changing the effective optimizer batch.
     mlx_max_microbatch_tokens: int = int(os.environ.get("MLX_MAX_MICROBATCH_TOKENS", 8_192))
@@ -143,6 +144,7 @@
         chunks.append(chunk)
         remaining -= chunk
     return chunks
+
 def accumulate_flat_grads(
     accum: dict[str, mx.array] | None,
     grads_tree: dict,
@@ -159,6 +161,7 @@
 # ==============================================================================
 def rms_norm(x: mx.array, eps: float = 1e-6) -> mx.array:
     return (x * mx.rsqrt(mx.mean(x * x, axis=-1, keepdims=True) + eps)).astype(x.dtype)
+
 def zeropower_newtonschulz5(g: mx.array, steps: int, eps: float = 1e-7) -> mx.array:
     # Orthogonalize a 2D update matrix with a fast Newton-Schulz iteration.
     # Muon uses this to normalize matrix-shaped gradients before applying them.
@@ -176,6 +179,7 @@
     if transposed:
         x = x.T
     return x.astype(g.dtype)
+
 def load_data_shard(path: Path) -> np.ndarray:
     header_bytes = 256 * np.dtype("<i4").itemsize
     token_bytes = np.dtype("<u2").itemsize
@@ -230,6 +234,7 @@
             self.pos += k
             left -= k
         return chunks[0] if len(chunks) == 1 else np.concatenate(chunks, axis=0)
+
 class TokenLoader:
     def __init__(
         self,
@@ -255,10 +260,12 @@
         self.weight = nn.Linear(in_dim, out_dim, bias=False).weight.astype(mx.float32)
     def __call__(self, x: mx.array) -> mx.array:
         return x @ self.weight.astype(x.dtype).T
+
 class RMSNormNoWeight(nn.Module):
     # MLX module wrapper around the functional RMSNorm helper so it composes nicely in blocks.
     def __call__(self, x: mx.array) -> mx.array:
         return rms_norm(x)
+
 class CausalSelfAttention(nn.Module):
     # - separate q/k/v projections
     # - RMSNorm on q and k before attention
@@ -301,6 +308,7 @@
         y = mx.fast.scaled_dot_product_attention(q, k, v, scale=self.scale, mask="causal")
         y = y.transpose(0, 2, 1, 3).reshape(bsz, seqlen, dim)
         return self.proj(y)
+
 class MLP(nn.Module):
     # Baseline MLP uses relu^2 instead of GELU/SiLU. It is cheap and works well in this setup.
     def __init__(self, dim: int, mlp_mult: int):
@@ -311,6 +319,7 @@
     def __call__(self, x: mx.array) -> mx.array:
         x = nn.relu(self.fc(x))
         return self.proj(x * x)
+
 class Block(nn.Module):
     def __init__(
         self,
@@ -336,6 +345,7 @@
         x = x + self.attn_scale.astype(x.dtype)[None, None, :] * attn_out
         x = x + self.mlp_scale.astype(x.dtype)[None, None, :] * self.mlp(self.mlp_norm(x))
         return x
+
 class GPT(nn.Module):
     # - token embedding + RMSNorm
     # - encoder half accumulates skip tensors
@@ -376,16 +386,11 @@
             x = self.blocks[i](x, x0)
             skips.append(x)
         for i in range(self.num_decoder_layers):
-            # Odd layer counts have one more decoder block than encoder block. The baseline only
-            # applies a skip connection when one exists, then runs the remaining decoder block(s)
-            # without an added skip.
             if skips:
                 x = x + self.skip_weights[i].astype(x.dtype)[None, None, :] * skips.pop()
             x = self.blocks[self.num_encoder_layers + i](x, x0)
         return self.final_norm(x)
     def loss(self, input_ids: mx.array, target_ids: mx.array) -> mx.array:
-        # Cross-entropy over flattened tokens. We keep optional logit chunking because it is a useful
-        # memory knob on Macs, but the common path is chunk_tokens=0 (single matmul + CE).
         x = self(input_ids).reshape(-1, self.tok_emb.weight.shape[1])
         y = target_ids.reshape(-1)
         if self.logit_chunk_tokens <= 0 or x.shape[0] <= self.logit_chunk_tokens:
@@ -425,8 +430,6 @@
 # OPTIMIZERS (MUON + ADAM SPLIT)
 # ==============================================================================
 class Muon:
-    # Muon applies SGD-momentum to matrix gradients, then orthogonalizes the result before the
-    # parameter update.
     def __init__(self, keys: list[str], params: dict[str, mx.array], args: Hyperparameters):
         self.keys = keys
         self.args = args
@@ -449,11 +452,8 @@
             scale = math.sqrt(max(1.0, float(p.shape[0]) / float(p.shape[1])))
             out[k] = p - lr * (g_ortho * scale).astype(p.dtype)
         return out
+
 class SplitOptimizers:
-    # - embeddings: Adam with the tied-embedding LR
-    # - block matrices (2D): Muon
-    # - block scalars + skip weights: Adam
-    # This preserves the high-level optimization behavior even though MLX internals differ.
     def __init__(self, model: GPT, args: Hyperparameters):
         self.args = args
         params = dict(tree_flatten(model.parameters()))
@@ -501,10 +501,6 @@
 # ==============================================================================
 # QUANTIZATION (INT8 + ZLIB)
 # ==============================================================================
-# - per-row int8 for 2D float tensors
-# - per-tensor int8 for other float tensors
-# - fp16 passthrough for small float tensors
-# - exact passthrough for non-floats
 MX_DTYPE_FROM_NAME = {
     "float32": mx.float32,
     "float16": mx.float16,
@@ -522,6 +518,7 @@
 )
 def _np_float32(arr: mx.array) -> np.ndarray:
     return np.array(arr.astype(mx.float32), dtype=np.float32, copy=False)
+
 def keep_float_array(name: str, arr: mx.array, passthrough_orig_dtypes: dict[str, str]) -> np.ndarray:
     if any(pattern in name for pattern in INT8_KEEP_FLOAT_FP32_NAME_PATTERNS):
         return np.ascontiguousarray(_np_float32(arr))
@@ -532,21 +529,20 @@
         passthrough_orig_dtypes[name] = str(arr.dtype).split(".")[-1]
         return np.ascontiguousarray(np.array(arr.astype(mx.float16), dtype=INT8_KEEP_FLOAT_STORE_DTYPE, copy=False))
     return np.ascontiguousarray(np.array(arr, copy=True))
+
 def quantize_float_array(arr: mx.array) -> tuple[np.ndarray, np.ndarray]:
     f32 = _np_float32(arr)
     if f32.ndim == 2:
-        # Matrices get one scale per row, which usually tracks output-channel
-        # ranges much better than a single tensor-wide scale.
         clip_abs = np.quantile(np.abs(f32), INT8_CLIP_Q, axis=1) if f32.size else np.empty((f32.shape[0],), dtype=np.float32)
         clipped = np.clip(f32, -clip_abs[:, None], clip_abs[:, None])
         scale = np.maximum(clip_abs / 127.0, 1.0 / 127.0).astype(np.float32, copy=False)
         q = np.clip(np.round(clipped / scale[:, None]), -127, 127).astype(np.int8, copy=False)
         return np.ascontiguousarray(q), np.ascontiguousarray(scale.astype(INT8_PER_ROW_SCALE_DTYPE, copy=False))
-    # Vectors / scalars use a simpler per-tensor scale.
     clip_abs = float(np.quantile(np.abs(f32).reshape(-1), INT8_CLIP_Q)) if f32.size else 0.0
     scale = np.array(clip_abs / 127.0 if clip_abs > 0.0 else 1.0, dtype=np.float32)
     q = np.clip(np.round(np.clip(f32, -clip_abs, clip_abs) / scale), -127, 127).astype(np.int8, copy=False)
     return np.ascontiguousarray(q), scale
+
 def quantize_state_dict_int8(flat_state: dict[str, mx.array]) -> tuple[dict[str, object], dict[str, int]]:
     quantized: dict[str, np.ndarray] = {}
     scales: dict[str, np.ndarray] = {}
@@ -567,8 +563,6 @@
             passthrough[name] = np.ascontiguousarray(np.array(arr))
             stats["int8_payload_bytes"] += int(passthrough[name].nbytes)
             continue
-        # Small float tensors are cheap enough to keep directly. We still downcast
-        # fp32/bf16 passthrough tensors to fp16 so metadata does not dominate size.
         if name in INT8_FP16_KEEP_NAMES or int(arr.size) <= INT8_KEEP_FLOAT_MAX_NUMEL:
             kept = keep_float_array(name, arr, passthrough_orig_dtypes)
             passthrough[name] = kept
@@ -594,6 +588,7 @@
     if passthrough_orig_dtypes:
         obj["passthrough_orig_dtypes"] = passthrough_orig_dtypes
     return obj, stats
+
 def dequantize_state_dict_int8(quant_obj: dict[str, object]) -> dict[str, mx.array]:
     out: dict[str, mx.array] = {}
     qmeta = quant_obj.get("qmeta", {})
@@ -603,13 +598,11 @@
         dtype_name = quant_obj["dtypes"][name]
         scale = np.asarray(quant_obj["scales"][name], dtype=np.float32)
         if qmeta.get(name, {}).get("scheme") == "per_row" or scale.ndim > 0:
-            # Broadcast the saved row scale back across trailing dimensions.
             out_arr = q_np.astype(np.float32) * scale.reshape((q_np.shape[0],) + (1,) * (q_np.ndim - 1))
         else:
             out_arr = q_np.astype(np.float32) * float(scale)
         out[name] = mx.array(out_arr, dtype=MX_DTYPE_FROM_NAME[dtype_name])
     for name, arr in quant_obj["passthrough"].items():
-        # Restore small tensors, undoing the temporary fp16 storage cast if needed.
         out_arr = np.array(arr, copy=True)
         orig_dtype = passthrough_orig_dtypes.get(name)
         if isinstance(orig_dtype, str):
@@ -617,6 +610,7 @@
         else:
             out[name] = mx.array(out_arr)
     return out
+
 def build_sentencepiece_luts(
     sp: spm.SentencePieceProcessor, vocab_size: int
 ) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
@@ -638,10 +632,8 @@
             piece = piece[1:]
         base_bytes_lut[token_id] = len(piece.encode("utf-8"))
     return base_bytes_lut, has_leading_space_lut, is_boundary_token_lut
+
 def validate_dataset_tokenizer_pair(data_path: str, tokenizer_path: str) -> tuple[str, int, int | None]:
-    # The shard directory and tokenizer are coupled: val_bpb is only meaningful if we
-    # decode bytes with the exact tokenizer that produced the shards. The manifest
-    # lets the training script fail fast on accidental dataset/tokenizer mismatches.
     dataset_dir = Path(data_path).resolve()
     actual_train_files = len(list(dataset_dir.glob("fineweb_train_*.bin")))
     if len(dataset_dir.parents) < 2:
@@ -671,16 +663,17 @@
                 f"manifest says {expected_train_files}"
             )
     return dataset_dir.name, actual_train_files, expected_train_files
+
 def load_validation_tokens(pattern: str, seq_len: int) -> np.ndarray:
     files = [Path(p) for p in sorted(glob.glob(pattern))]
     if not files:
         raise FileNotFoundError(f"No files found for pattern: {pattern}")
-    # The export pipeline writes the fixed first-50k-doc validation set to fineweb_val_*.
     tokens = np.ascontiguousarray(np.concatenate([load_data_shard(file) for file in files], axis=0))
     usable = ((tokens.size - 1) // seq_len) * seq_len
     if usable <= 0:
-        raise ValueError(f"Validation split is too short for TRAIN_SEQ_LEN={seq_len}")
+        raise ValueError(f"Validation split is too short for EVAL_SEQ_LEN={seq_len}")
     return tokens[: usable + 1]
+
 def build_validation_doc_spans(tokens: np.ndarray, bos_token_id: int) -> list[tuple[int, int]]:
     if bos_token_id < 0:
         return [(0, int(tokens.size))]
@@ -694,6 +687,7 @@
         if end - start_i >= 2:
             spans.append((start_i, end))
     return spans if spans else [(0, int(tokens.size))]
+
 def count_doc_eval_windows(total_targets: int, seq_len: int, stride: int) -> int:
     if total_targets <= 0:
         return 0
@@ -701,6 +695,7 @@
         return max((total_targets + seq_len - 1) // seq_len, 1)
     remaining = max(total_targets - seq_len, 0)
     return 1 + (remaining + stride - 1) // stride
+
 def fill_doc_window(
     doc_tokens: np.ndarray,
     seq_len: int,
@@ -725,6 +720,7 @@
         y_row[:] = chunk[1:]
     mask_row.fill(0.0)
     mask_row[-score_tokens:] = 1.0
+
 def eval_val_doc_isolated(
     args: Hyperparameters,
     compiled_masked_loss,
@@ -736,23 +732,24 @@
     is_boundary_token_lut: np.ndarray,
     log_fn: Callable[[str], None] | None = None,
 ) -> tuple[float, float]:
+    seq_len = args.eval_seq_len
     val_batch_tokens = args.val_batch_size // args.grad_accum_steps
-    if val_batch_tokens < args.train_seq_len:
+    if val_batch_tokens < seq_len:
         raise ValueError(
-            "VAL_BATCH_SIZE must provide at least one sequence; "
+            "VAL_BATCH_SIZE must provide at least one eval sequence; "
             f"got VAL_BATCH_SIZE={args.val_batch_size}, GRAD_ACCUM_STEPS={args.grad_accum_steps}, "
-            f"TRAIN_SEQ_LEN={args.train_seq_len}"
+            f"EVAL_SEQ_LEN={seq_len}"
         )
-    val_batch_seqs = val_batch_tokens // args.train_seq_len
-    total_windows = sum(count_doc_eval_windows(end - start - 1, args.train_seq_len, args.eval_stride) for start, end in doc_spans)
+    val_batch_seqs = val_batch_tokens // seq_len
+    total_windows = sum(count_doc_eval_windows(end - start - 1, seq_len, args.eval_stride) for start, end in doc_spans)
     total_batches = max((total_windows + val_batch_seqs - 1) // val_batch_seqs, 1)
     total_loss_sum = 0.0
     total_tokens = 0.0
     total_bytes = 0.0
     batch_idx = 0
-    x_np = np.empty((val_batch_seqs, args.train_seq_len), dtype=np.int32)
+    x_np = np.empty((val_batch_seqs, seq_len), dtype=np.int32)
     y_np = np.empty_like(x_np)
-    mask_np = np.zeros((val_batch_seqs, args.train_seq_len), dtype=np.float32)
+    mask_np = np.zeros((val_batch_seqs, seq_len), dtype=np.float32)
     pending = 0
     batch_token_count = 0.0
     batch_bytes = 0.0
@@ -779,14 +776,14 @@
         total_doc_targets = int(doc_tokens.size - 1)
         if total_doc_targets <= 0:
             continue
-        if args.eval_stride <= 0 or args.eval_stride >= args.train_seq_len:
+        if args.eval_stride <= 0 or args.eval_stride >= seq_len:
             score_end = 0
             while score_end < total_doc_targets:
-                next_score_end = min(score_end + args.train_seq_len, total_doc_targets)
+                next_score_end = min(score_end + seq_len, total_doc_targets)
                 score_tokens = next_score_end - score_end
                 fill_doc_window(
                     doc_tokens,
-                    args.train_seq_len,
+                    seq_len,
                     bos_token_id,
                     next_score_end,
                     score_tokens,
@@ -808,13 +805,13 @@
                     batch_token_count, batch_bytes = flush_batch(pending, batch_token_count, batch_bytes)
                     pending = 0
             continue
-        score_end = min(args.train_seq_len, total_doc_targets)
+        score_end = min(seq_len, total_doc_targets)
         prev_score_end = 0
         while True:
             score_tokens = score_end - prev_score_end
             fill_doc_window(
                 doc_tokens,
-                args.train_seq_len,
+                seq_len,
                 bos_token_id,
                 score_end,
                 score_tokens,
@@ -844,6 +841,7 @@
     bits_per_token = val_loss / math.log(2.0)
     val_bpb = bits_per_token * (total_tokens / total_bytes)
     return val_loss, val_bpb
+
 def loss_and_grad_chunked(
     args: Hyperparameters,
     train_loader: TokenLoader,
@@ -860,8 +858,9 @@
         loss_value = loss_value + loss.astype(mx.float32) * scale
         grad_accum = accumulate_flat_grads(grad_accum, grads, scale)
         if args.mlx_eager_eval:
-            mx.eval(loss_value, grad_accum)  # materialize each chunk to cap peak memory
+            mx.eval(loss_value, grad_accum)
     return loss_value, tree_unflatten(list(grad_accum.items()))
+
 def loss_and_grad_one_batch(
     args: Hyperparameters,
     train_loader: TokenLoader,
@@ -869,6 +868,7 @@
 ) -> tuple[mx.array, dict]:
     x, y = train_loader.next_batch(args.train_batch_tokens, args.train_seq_len)
     return compiled_loss_and_grad(x, y)
+
 def eval_val(
     args: Hyperparameters,
     compiled_loss,
@@ -881,9 +881,7 @@
     is_boundary_token_lut: np.ndarray,
     log_fn: Callable[[str], None] | None = None,
 ) -> tuple[float, float]:
-    # Validation computes two metrics:
-    # - val_loss: token cross-entropy (natural log)
-    # - val_bpb: tokenizer-agnostic compression metric used by the challenge
+    seq_len = args.eval_seq_len
     if args.eval_doc_isolated and doc_spans is not None and bos_token_id >= 0:
         return eval_val_doc_isolated(
             args,
@@ -897,26 +895,26 @@
             log_fn=log_fn,
         )
     val_batch_tokens = args.val_batch_size // args.grad_accum_steps
-    if val_batch_tokens < args.train_seq_len:
+    if val_batch_tokens < seq_len:
         raise ValueError(
-            "VAL_BATCH_SIZE must provide at least one sequence; "
+            "VAL_BATCH_SIZE must provide at least one eval sequence; "
             f"got VAL_BATCH_SIZE={args.val_batch_size}, GRAD_ACCUM_STEPS={args.grad_accum_steps}, "
-            f"TRAIN_SEQ_LEN={args.train_seq_len}"
+            f"EVAL_SEQ_LEN={seq_len}"
         )
-    val_batch_seqs = val_batch_tokens // args.train_seq_len
-    if args.eval_stride <= 0 or args.eval_stride >= args.train_seq_len:
-        total_seqs = (val_tokens.size - 1) // args.train_seq_len
+    val_batch_seqs = val_batch_tokens // seq_len
+    if args.eval_stride <= 0 or args.eval_stride >= seq_len:
+        total_seqs = (val_tokens.size - 1) // seq_len
         total_batches = max((total_seqs + val_batch_seqs - 1) // val_batch_seqs, 1)
         total_loss_sum = 0.0
         total_tokens = 0.0
         total_bytes = 0.0
         for batch_idx, batch_seq_start in enumerate(range(0, total_seqs, val_batch_seqs), start=1):
             batch_seq_end = min(batch_seq_start + val_batch_seqs, total_seqs)
-            raw_start = batch_seq_start * args.train_seq_len
-            raw_end = batch_seq_end * args.train_seq_len + 1
+            raw_start = batch_seq_start * seq_len
+            raw_end = batch_seq_end * seq_len + 1
             chunk = val_tokens[raw_start:raw_end]
-            x_np = chunk[:-1].reshape(-1, args.train_seq_len)
-            y_np = chunk[1:].reshape(-1, args.train_seq_len)
+            x_np = chunk[:-1].reshape(-1, seq_len)
+            y_np = chunk[1:].reshape(-1, seq_len)
             x = mx.array(x_np, dtype=mx.int32)
             y = mx.array(y_np, dtype=mx.int32)
             chunk_token_count = float(y.size)
@@ -941,26 +939,26 @@
         return val_loss, val_bpb
     stride = args.eval_stride
     available_targets = val_tokens.size - 1
-    usable_targets = args.train_seq_len + max(((available_targets - args.train_seq_len) // stride), 0) * stride
-    total_windows = 1 + max((usable_targets - args.train_seq_len) // stride, 0)
+    usable_targets = seq_len + max(((available_targets - seq_len) // stride), 0) * stride
+    total_windows = 1 + max((usable_targets - seq_len) // stride, 0)
     total_batches = max((total_windows + val_batch_seqs - 1) // val_batch_seqs, 1)
     total_loss_sum = 0.0
     total_tokens = 0.0
     total_bytes = 0.0
     for batch_idx, window_idx_start in enumerate(range(0, total_windows, val_batch_seqs), start=1):
         window_idx_end = min(window_idx_start + val_batch_seqs, total_windows)
-        x_np = np.empty((window_idx_end - window_idx_start, args.train_seq_len), dtype=np.int32)
+        x_np = np.empty((window_idx_end - window_idx_start, seq_len), dtype=np.int32)
         y_np = np.empty_like(x_np)
-        mask_np = np.zeros((window_idx_end - window_idx_start, args.train_seq_len), dtype=np.float32)
+        mask_np = np.zeros((window_idx_end - window_idx_start, seq_len), dtype=np.float32)
         batch_token_count = 0.0
         batch_bytes = 0.0
         for local_idx, window_idx in enumerate(range(window_idx_start, window_idx_end)):
             raw_start = window_idx * stride
-            raw_end = raw_start + args.train_seq_len
+            raw_end = raw_start + seq_len
             chunk = val_tokens[raw_start : raw_end + 1]
             x_np[local_idx] = chunk[:-1]
             y_np[local_idx] = chunk[1:]
-            score_tokens = args.train_seq_len if window_idx == 0 else stride
+            score_tokens = seq_len if window_idx == 0 else stride
             mask_np[local_idx, -score_tokens:] = 1.0
             prev_ids = x_np[local_idx, -score_tokens:]
             tgt_ids = y_np[local_idx, -score_tokens:]
@@ -986,6 +984,7 @@
     bits_per_token = val_loss / math.log(2.0)
     val_bpb = bits_per_token * (total_tokens / total_bytes)
     return val_loss, val_bpb
+
 def estimate_eval_time_ms(
     args: Hyperparameters,
     compiled_loss,
@@ -994,18 +993,19 @@
     doc_spans: list[tuple[int, int]] | None,
     bos_token_id: int,
 ) -> float:
+    seq_len = args.eval_seq_len
     if args.eval_doc_isolated and doc_spans is not None and bos_token_id >= 0:
         val_batch_tokens = args.val_batch_size // args.grad_accum_steps
-        if val_batch_tokens < args.train_seq_len:
+        if val_batch_tokens < seq_len:
             raise ValueError(
-                "VAL_BATCH_SIZE must provide at least one sequence; "
+                "VAL_BATCH_SIZE must provide at least one eval sequence; "
                 f"got VAL_BATCH_SIZE={args.val_batch_size}, GRAD_ACCUM_STEPS={args.grad_accum_steps}, "
-                f"TRAIN_SEQ_LEN={args.train_seq_len}"
+                f"EVAL_SEQ_LEN={seq_len}"
             )
-        val_batch_seqs = val_batch_tokens // args.train_seq_len
+        val_batch_seqs = val_batch_tokens // seq_len
         total_units = max(
             (
-                sum(count_doc_eval_windows(end - start - 1, args.train_seq_len, args.eval_stride) for start, end in doc_spans)
+                sum(count_doc_eval_windows(end - start - 1, seq_len, args.eval_stride) for start, end in doc_spans)
                 + val_batch_seqs
                 - 1
             )
@@ -1013,9 +1013,9 @@
             1,
         )
         sample_units = min(max(args.final_eval_estimate_batches, 1), total_units)
-        x_np = np.empty((val_batch_seqs, args.train_seq_len), dtype=np.int32)
+        x_np = np.empty((val_batch_seqs, seq_len), dtype=np.int32)
         y_np = np.empty_like(x_np)
-        mask_np = np.zeros((val_batch_seqs, args.train_seq_len), dtype=np.float32)
+        mask_np = np.zeros((val_batch_seqs, seq_len), dtype=np.float32)
         start = time.perf_counter()
         pending = 0
         seen_units = 0
@@ -1024,13 +1024,13 @@
             total_doc_targets = int(doc_tokens.size - 1)
             if total_doc_targets <= 0:
                 continue
-            if args.eval_stride <= 0 or args.eval_stride >= args.train_seq_len:
+            if args.eval_stride <= 0 or args.eval_stride >= seq_len:
                 score_end = 0
                 while score_end < total_doc_targets:
-                    next_score_end = min(score_end + args.train_seq_len, total_doc_targets)
+                    next_score_end = min(score_end + seq_len, total_doc_targets)
                     fill_doc_window(
                         doc_tokens,
-                        args.train_seq_len,
+                        seq_len,
                         bos_token_id,
                         next_score_end,
                         next_score_end - score_end,
@@ -1054,12 +1054,12 @@
                             sample_ms = 1000.0 * (time.perf_counter() - start)
                             return sample_ms * total_units / max(sample_units, 1)
                 continue
-            score_end = min(args.train_seq_len, total_doc_targets)
+            score_end = min(seq_len, total_doc_targets)
             prev_score_end = 0
             while True:
                 fill_doc_window(
                     doc_tokens,
-                    args.train_seq_len,
+                    seq_len,
                     bos_token_id,
                     score_end,
                     score_end - prev_score_end,
@@ -1097,24 +1097,24 @@
         sample_ms = 1000.0 * (time.perf_counter() - start)
         return sample_ms * total_units / max(seen_units, 1)
     val_batch_tokens = args.val_batch_size // args.grad_accum_steps
-    if val_batch_tokens < args.train_seq_len:
+    if val_batch_tokens < seq_len:
         raise ValueError(
-            "VAL_BATCH_SIZE must provide at least one sequence; "
+            "VAL_BATCH_SIZE must provide at least one eval sequence; "
             f"got VAL_BATCH_SIZE={args.val_batch_size}, GRAD_ACCUM_STEPS={args.grad_accum_steps}, "
-            f"TRAIN_SEQ_LEN={args.train_seq_len}"
+            f"EVAL_SEQ_LEN={seq_len}"
         )
-    val_batch_seqs = val_batch_tokens // args.train_seq_len
-    if args.eval_stride <= 0 or args.eval_stride >= args.train_seq_len:
-        total_units = max(((val_tokens.size - 1) // args.train_seq_len + val_batch_seqs - 1) // val_batch_seqs, 1)
+    val_batch_seqs = val_batch_tokens // seq_len
+    if args.eval_stride <= 0 or args.eval_stride >= seq_len:
+        total_units = max(((val_tokens.size - 1) // seq_len + val_batch_seqs - 1) // val_batch_seqs, 1)
         sample_units = min(max(args.final_eval_estimate_batches, 1), total_units)
         start = time.perf_counter()
-        for batch_idx, batch_seq_start in enumerate(range(0, (val_tokens.size - 1) // args.train_seq_len, val_batch_seqs), start=1):
-            batch_seq_end = min(batch_seq_start + val_batch_seqs, (val_tokens.size - 1) // args.train_seq_len)
-            raw_start = batch_seq_start * args.train_seq_len
-            raw_end = batch_seq_end * args.train_seq_len + 1
+        for batch_idx, batch_seq_start in enumerate(range(0, (val_tokens.size - 1) // seq_len, val_batch_seqs), start=1):
+            batch_seq_end = min(batch_seq_start + val_batch_seqs, (val_tokens.size - 1) // seq_len)
+            raw_start = batch_seq_start * seq_len
+            raw_end = batch_seq_end * seq_len + 1
             chunk = val_tokens[raw_start:raw_end]
-            x = mx.array(chunk[:-1].reshape(-1, args.train_seq_len), dtype=mx.int32)
-            y = mx.array(chunk[1:].reshape(-1, args.train_seq_len), dtype=mx.int32)
+            x = mx.array(chunk[:-1].reshape(-1, seq_len), dtype=mx.int32)
+            y = mx.array(chunk[1:].reshape(-1, seq_len), dtype=mx.int32)
             batch_loss = compiled_loss(x, y).astype(mx.float32)
             mx.eval(batch_loss)
             if batch_idx >= sample_units:
@@ -1124,23 +1124,23 @@
         return sample_ms * total_units / max(sample_units, 1)
     stride = args.eval_stride
     available_targets = val_tokens.size - 1
-    usable_targets = args.train_seq_len + max(((available_targets - args.train_seq_len) // stride), 0) * stride
-    total_windows = 1 + max((usable_targets - args.train_seq_len) // stride, 0)
+    usable_targets = seq_len + max(((available_targets - seq_len) // stride), 0) * stride
+    total_windows = 1 + max((usable_targets - seq_len) // stride, 0)
     total_units = max((total_windows + val_batch_seqs - 1) // val_batch_seqs, 1)
     sample_units = min(max(args.final_eval_estimate_batches, 1), total_units)
     start = time.perf_counter()
     for batch_idx, window_idx_start in enumerate(range(0, total_windows, val_batch_seqs), start=1):
         window_idx_end = min(window_idx_start + val_batch_seqs, total_windows)
-        x_np = np.empty((window_idx_end - window_idx_start, args.train_seq_len), dtype=np.int32)
+        x_np = np.empty((window_idx_end - window_idx_start, seq_len), dtype=np.int32)
         y_np = np.empty_like(x_np)
-        mask_np = np.zeros((window_idx_end - window_idx_start, args.train_seq_len), dtype=np.float32)
+        mask_np = np.zeros((window_idx_end - window_idx_start, seq_len), dtype=np.float32)
         for local_idx, window_idx in enumerate(range(window_idx_start, window_idx_end)):
             raw_start = window_idx * stride
-            raw_end = raw_start + args.train_seq_len
+            raw_end = raw_start + seq_len
             chunk = val_tokens[raw_start : raw_end + 1]
             x_np[local_idx] = chunk[:-1]
             y_np[local_idx] = chunk[1:]
-            score_tokens = args.train_seq_len if window_idx == 0 else stride
+            score_tokens = seq_len if window_idx == 0 else stride
             mask_np[local_idx, -score_tokens:] = 1.0
         x = mx.array(x_np, dtype=mx.int32)
         y = mx.array(y_np, dtype=mx.int32)
@@ -1169,10 +1169,8 @@
         return grads_tree
     scale = max_norm / (total_norm + 1e-12)
     return tree_unflatten([(k, g * scale) for k, g in flat.items()])
+
 def main() -> None:
-    # ==============================================================================
-    # TOKENIZER + VALIDATION METRIC SETUP
-    # ==============================================================================
     args = Hyperparameters()
     out_dir = Path(args.out_dir)
     out_dir.mkdir(parents=True, exist_ok=True)
@@ -1202,20 +1200,14 @@
         args.data_path,
         args.tokenizer_path,
     )
-    val_tokens = load_validation_tokens(args.val_files, args.train_seq_len)
+    val_tokens = load_validation_tokens(args.val_files, args.eval_seq_len)
     bos_token_id = int(sp.bos_id())
     doc_spans = build_validation_doc_spans(val_tokens, bos_token_id) if bos_token_id >= 0 else None
     base_bytes_lut, has_leading_space_lut, is_boundary_token_lut = build_sentencepiece_luts(
         sp, args.vocab_size
     )
-    # ==============================================================================
-    # TRAINING SETUP
-    # ==============================================================================
     mx.random.seed(args.seed)
     train_loader = TokenLoader(args.train_files, log_fn=log, dataset_name=dataset_name)
-    # ==============================================================================
-    # MODEL + OPTIMIZER SETUP
-    # ==============================================================================
     model = GPT(
         vocab_size=args.vocab_size,
         num_layers=args.num_layers,
@@ -1230,13 +1222,6 @@
         qk_gain_init=args.qk_gain_init,
     )
     opt = SplitOptimizers(model, args)
-    # ==============================================================================
-    # COMPILED TRAIN / EVAL FUNCTIONS (MLX)
-    # ==============================================================================
-    # The crucial MLX detail is capture scope: this model contains non-trainable arrays too (for example
-    # inside RoPE modules), so compiling only against trainable parameters throws "uncaptured inputs".
-    # Compiling the model-bound functions and capturing the full model state fixes that while still
-    # returning gradients only for trainable parameters via nn.value_and_grad(...).
     compiled_loss = mx.compile(lambda x, y: model.loss(x, y), inputs=model.state, outputs=model.state)
     compiled_masked_loss = mx.compile(
         lambda x, y, m: model.masked_loss(x, y, m),
@@ -1249,7 +1234,6 @@
         outputs=model.state,
     )
     train_step_loss_and_grad = loss_and_grad_one_batch if args.use_single_microbatch_path else loss_and_grad_chunked
-    # Print config once so logs are self-describing.
     n_params = sum(int(np.prod(p.shape)) for _, p in tree_flatten(model.parameters()))
     log(f"run_id:{args.run_id}")
     log(f"mlx_version:{mx.__version__}")
@@ -1269,19 +1253,18 @@
     log(
         f"model_params:{n_params} vocab_size:{args.vocab_size} layers:{args.num_layers} "
         f"dim:{args.model_dim} heads:{args.num_heads} kv_heads:{args.num_kv_heads} "
-        f"seq_len:{args.train_seq_len} tie_embeddings:{args.tie_embeddings}"
+        f"train_seq_len:{args.train_seq_len} eval_seq_len:{args.eval_seq_len} tie_embeddings:{args.tie_embeddings}"
     )
     log(
         f"iterations:{args.iterations} train_batch_tokens:{args.train_batch_tokens} grad_accum_steps:{args.grad_accum_steps} "
         f"microbatch_tokens:{args.microbatch_tokens} microbatch_batch_size:{args.microbatch_tokens // args.train_seq_len} "
-        f"val_batch_size:{args.val_batch_size} "
-        f"warmup_steps:{args.warmup_steps} max_wallclock_seconds:{args.max_wallclock_seconds:.3f}"
+        f"val_batch_size:{args.val_batch_size} warmup_steps:{args.warmup_steps} "
+        f"max_wallclock_seconds:{args.max_wallclock_seconds:.3f}"
     )
     log(f"mlx_max_microbatch_tokens:{args.mlx_max_microbatch_tokens}")
     log(
         f"optimizer:muon+adam muon_matrix_params:{len(opt.matrix_keys)} scalar_params:{len(opt.scalar_keys)} "
-        f"embed_lr:{args.tied_embed_lr} "
-        f"matrix_lr:{args.matrix_lr} scalar_lr:{args.scalar_lr} "
+        f"embed_lr:{args.tied_embed_lr} matrix_lr:{args.matrix_lr} scalar_lr:{args.scalar_lr} "
         f"muon_momentum:{args.muon_momentum} muon_steps:{args.muon_backend_steps}"
     )
     log(f"val_bpb:enabled tokenizer_kind=sentencepiece tokenizer_path={args.tokenizer_path}")
@@ -1310,14 +1293,7 @@
         f"final_eval_budget:estimate_ms:{estimated_final_eval_ms:.0f} "
         f"reserve_ms:{reserved_final_ms:.0f} estimate_batches:{args.final_eval_estimate_batches}"
     )
-    # ==============================================================================
-    # TRAINING LOOP
-    # ==============================================================================
     if args.warmup_steps > 0:
-        # Warmup should only prime MLX compile/allocation paths. Updating parameters here forces us
-        # to snapshot and restore model/optimizer state, which is expensive on unified-memory Macs.
-        # Instead we run the real train shapes, force the loss/grads to materialize, and then reset
-        # the loader so measured training still starts from the true init and token window.
         for warmup_step in range(args.warmup_steps):
             accum: dict[str, mx.array] | None = None
             warmup_loss = mx.array(0.0, dtype=mx.float32)
@@ -1329,18 +1305,17 @@
             mx.synchronize()
             if args.warmup_steps <= 20 or (warmup_step + 1) % 10 == 0 or warmup_step + 1 == args.warmup_steps:
                 log(f"warmup_step:{warmup_step + 1}/{args.warmup_steps}")
-        # Prime the standalone eval graph once too. It is compiled separately from value_and_grad.
         val_batch_tokens = args.val_batch_size // args.grad_accum_steps
-        if val_batch_tokens < args.train_seq_len:
+        if val_batch_tokens < args.eval_seq_len:
             raise ValueError(
-                "VAL_BATCH_SIZE must provide at least one sequence; "
+                "VAL_BATCH_SIZE must provide at least one eval sequence; "
                 f"got VAL_BATCH_SIZE={args.val_batch_size}, GRAD_ACCUM_STEPS={args.grad_accum_steps}, "
-                f"TRAIN_SEQ_LEN={args.train_seq_len}"
+                f"EVAL_SEQ_LEN={args.eval_seq_len}"
             )
-        warm_val_seqs = min(val_batch_tokens // args.train_seq_len, (val_tokens.size - 1) // args.train_seq_len)
-        warm_chunk = val_tokens[: warm_val_seqs * args.train_seq_len + 1]
-        x_val = mx.array(warm_chunk[:-1].reshape(-1, args.train_seq_len), dtype=mx.int32)
-        y_val = mx.array(warm_chunk[1:].reshape(-1, args.train_seq_len), dtype=mx.int32)
+        warm_val_seqs = min(val_batch_tokens // args.eval_seq_len, (val_tokens.size - 1) // args.eval_seq_len)
+        warm_chunk = val_tokens[: warm_val_seqs * args.eval_seq_len + 1]
+        x_val = mx.array(warm_chunk[:-1].reshape(-1, args.eval_seq_len), dtype=mx.int32)
+        y_val = mx.array(warm_chunk[1:].reshape(-1, args.eval_seq_len), dtype=mx.int32)
         warm_mask = mx.ones(x_val.shape, dtype=mx.float32)
         warm_val_loss = compiled_masked_loss(x_val, y_val, warm_mask)
         mx.eval(warm_val_loss)
@@ -1355,7 +1330,6 @@
         last_step = step == args.iterations or (stop_after_step is not None and step >= stop_after_step)
         if last_step or (args.val_loss_every > 0 and step % args.val_loss_every == 0):
             train_time_ms += 1000.0 * (time.perf_counter() - t0)
-            # Validation always scans the same fixed full validation split.
             val_loss, val_bpb = eval_val(
                 args,
                 compiled_loss,
@@ -1395,7 +1369,7 @@
                 accum = accumulate_flat_grads(accum, grads, grad_scale)
                 train_loss = train_loss + loss.astype(mx.float32) * grad_scale
                 if args.mlx_eager_eval:
-                    mx.eval(train_loss, accum)  # materialize each microbatch to cap peak memory
+                    mx.eval(train_loss, accum)
             grads = tree_unflatten(list(accum.items()))
             grads = clip_grad_tree(grads, args.grad_clip_norm)
             train_loss_value = float(train_loss.item())
@@ -1416,12 +1390,6 @@
             and approx_train_time_ms >= max(max_wallclock_ms - reserved_final_ms, 0.0)
         ):
             stop_after_step = step
-    # ==============================================================================
-    # FINAL SERIALIZATION + QUANTIZED ROUNDTRIP EVAL
-    # ==============================================================================
-    # We always write a raw artifact and a quantized artifact, then validate the
-    # quantized roundtrip directly by loading the dequantized tensors back into the
-    # model and running one final validation pass.
     out_path = out_dir / f"{args.run_id}_mlx_model.npz"
     flat_state = {k: v for k, v in tree_flatten(model.state)}
     mx.savez(str(out_path), **flat_state)
```

## Result

Ran local MLX Parameter Golf in official-like mode on the Mac mini. Final val_bpb=2.3236, val_loss=3.9280, quantized artifact=10414733 bytes. Modified script used. Throughput: 13942 tok/s. Memory: 316MB peak, 316MB active. Score=2.3236. Expected signal: Higher step count and total train tokens within 600s, with final eval quality holding up because RoPE can score at 1024 even when trained at 512. If undertraining is the main bottleneck, val_bpb should improve despite shorter training context.
