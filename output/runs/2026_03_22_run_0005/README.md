# Time-Aware Hold-Then-Decay Schedule With Tighter Final-Eval Reserve

**Score:** 2.320695 val_bpb
**Hardware:** Apple Silicon Mac mini M4 16GB (600s wallclock cap; step count depends on the script)
**Runtime:** 211s

## Approach

Run 0004 preserved the Mac-mini baseline, but its current wallclock-aware LR logic effectively decays across almost the entire 10-minute run because only ~15 steps fit in budget. That is the wrong shape for this regime. This patch compounds the current best script by keeping LR flat through most of the run, then decaying only near the end, while also tightening the final-eval reserve and using a rolling step-time predictor so training stops after the last safe high-value step instead of leaving extra budget idle.

## Changes

```diff
--- a/train_gpt_mlx.py
+++ b/train_gpt_mlx.py
@@ -58,10 +58,14 @@
     warmup_steps: int = int(os.environ.get("WARMUP_STEPS", 0))
     warmdown_iters: int = int(os.environ.get("WARMDOWN_ITERS", 15))
     max_wallclock_seconds: float = float(os.environ.get("MAX_WALLCLOCK_SECONDS", 600.0))
-    final_eval_reserve_seconds: float = float(os.environ.get("FINAL_EVAL_RESERVE_SECONDS", 90.0))
-    final_eval_reserve_scale: float = float(os.environ.get("FINAL_EVAL_RESERVE_SCALE", 1.35))
+    final_eval_reserve_seconds: float = float(os.environ.get("FINAL_EVAL_RESERVE_SECONDS", 45.0))
+    final_eval_reserve_scale: float = float(os.environ.get("FINAL_EVAL_RESERVE_SCALE", 1.15))
     final_eval_estimate_batches: int = int(os.environ.get("FINAL_EVAL_ESTIMATE_BATCHES", 2))
-    final_eval_serialization_seconds: float = float(os.environ.get("FINAL_EVAL_SERIALIZATION_SECONDS", 5.0))
+    final_eval_serialization_seconds: float = float(os.environ.get("FINAL_EVAL_SERIALIZATION_SECONDS", 3.0))
+    lr_decay_start_frac: float = float(os.environ.get("LR_DECAY_START_FRAC", 0.70))
+    lr_min_frac: float = float(os.environ.get("LR_MIN_FRAC", 0.15))
+    next_step_margin: float = float(os.environ.get("NEXT_STEP_MARGIN", 1.05))
+    step_predictor_beta: float = float(os.environ.get("STEP_PREDICTOR_BETA", 0.80))
     # Model (defaults match the current baseline setup).
     vocab_size: int = int(os.environ.get("VOCAB_SIZE", 1024))
     num_layers: int = int(os.environ.get("NUM_LAYERS", 9))
@@ -106,15 +110,27 @@
             and self.microbatch_tokens <= self.mlx_max_microbatch_tokens
         )
     def lr_mul(self, step: int, elapsed_ms: float) -> float:
+        warmup_mul = 1.0
+        if self.warmup_steps > 0:
+            warmup_mul = min((step + 1) / max(self.warmup_steps, 1), 1.0)
+        decay_start = min(max(self.lr_decay_start_frac, 0.0), 0.999999)
+        lr_floor = min(max(self.lr_min_frac, 0.0), 1.0)
+        if self.max_wallclock_seconds > 0:
+            progress = min(max(elapsed_ms / (1000.0 * self.max_wallclock_seconds), 0.0), 1.0)
+            if progress <= decay_start:
+                return warmup_mul
+            decay_t = min(max((progress - decay_start) / max(1.0 - decay_start, 1e-9), 0.0), 1.0)
+            cosine = 0.5 * (1.0 + math.cos(math.pi * decay_t))
+            return warmup_mul * (lr_floor + (1.0 - lr_floor) * cosine)
         if self.warmdown_iters <= 0:
-            return 1.0
-        if self.max_wallclock_seconds <= 0:
-            warmdown_start = max(self.iterations - self.warmdown_iters, 0)
-            return max((self.iterations - step) / max(self.warmdown_iters, 1), 0.0) if warmdown_start <= step < self.iterations else 1.0
-        step_ms = elapsed_ms / max(step, 1)
-        warmdown_ms = self.warmdown_iters * step_ms
-        remaining_ms = max(1000.0 * self.max_wallclock_seconds - elapsed_ms, 0.0)
-        return remaining_ms / max(warmdown_ms, 1e-9) if remaining_ms <= warmdown_ms else 1.0
+            return warmup_mul
+        decay_steps = max(self.warmdown_iters, 1)
+        hold_steps = max(self.iterations - decay_steps, 0)
+        if step < hold_steps:
+            return warmup_mul
+        decay_t = min(max((step - hold_steps) / decay_steps, 0.0), 1.0)
+        cosine = 0.5 * (1.0 + math.cos(math.pi * decay_t))
+        return warmup_mul * (lr_floor + (1.0 - lr_floor) * cosine)
 CONTROL_TENSOR_NAME_PATTERNS = tuple(
     pattern
     for pattern in os.environ.get(
@@ -1284,6 +1300,10 @@
         f"matrix_lr:{args.matrix_lr} scalar_lr:{args.scalar_lr} "
         f"muon_momentum:{args.muon_momentum} muon_steps:{args.muon_backend_steps}"
     )
+    log(
+        f"lr_schedule:decay_start_frac:{args.lr_decay_start_frac:.2f} lr_min_frac:{args.lr_min_frac:.2f} "
+        f"next_step_margin:{args.next_step_margin:.3f} step_predictor_beta:{args.step_predictor_beta:.2f}"
+    )
     log(f"val_bpb:enabled tokenizer_kind=sentencepiece tokenizer_path={args.tokenizer_path}")
     eval_mode = "doc_isolated_sliding" if args.eval_doc_isolated and doc_spans is not None and bos_token_id >= 0 else "flat_stream"
     log(f"eval_mode:{eval_mode} bos_token_id:{bos_token_id} val_docs:{0 if doc_spans is None else len(doc_spans)}")
@@ -1349,6 +1369,7 @@
     train_time_ms = 0.0
     max_wallclock_ms = 1000.0 * args.max_wallclock_seconds if args.max_wallclock_seconds > 0 else None
     stop_after_step: int | None = None
+    step_ema_ms: float | None = None
     t0 = time.perf_counter()
     step = 0
     while True:
@@ -1402,20 +1423,24 @@
         opt.step(model, grads, step=step, lr_mul=lr_mul)
         mx.synchronize()
         step_ms = 1000.0 * (time.perf_counter() - step_t0)
+        step_ema_ms = step_ms if step_ema_ms is None else args.step_predictor_beta * step_ema_ms + (1.0 - args.step_predictor_beta) * step_ms
         approx_train_time_ms = train_time_ms + 1000.0 * (time.perf_counter() - t0)
         tok_s = args.train_batch_tokens / (step_ms / 1000.0)
         step += 1
         if args.train_log_every > 0 and (step <= 10 or step % args.train_log_every == 0 or stop_after_step is not None):
             log(
                 f"step:{step}/{args.iterations} train_loss:{train_loss_value:.4f} "
-                f"train_time:{approx_train_time_ms:.0f}ms step_avg:{approx_train_time_ms / step:.2f}ms tok_s:{tok_s:.0f}"
+                f"lr_mul:{lr_mul:.4f} train_time:{approx_train_time_ms:.0f}ms "
+                f"step_avg:{approx_train_time_ms / step:.2f}ms tok_s:{tok_s:.0f}"
             )
-        if (
-            max_wallclock_ms is not None
-            and stop_after_step is None
-            and approx_train_time_ms >= max(max_wallclock_ms - reserved_final_ms, 0.0)
-        ):
-            stop_after_step = step
+        if max_wallclock_ms is not None and stop_after_step is None:
+            predicted_next_step_ms = (step_ema_ms if step_ema_ms is not None else step_ms) * args.next_step_margin
+            if approx_train_time_ms + predicted_next_step_ms >= max(max_wallclock_ms - reserved_final_ms, 0.0):
+                stop_after_step = step
+                log(
+                    f"stop_prediction:after_step:{step} train_time:{approx_train_time_ms:.0f}ms "
+                    f"pred_next_step_ms:{predicted_next_step_ms:.0f} reserve_ms:{reserved_final_ms:.0f}"
+                )
     # ==============================================================================
     # FINAL SERIALIZATION + QUANTIZED ROUNDTRIP EVAL
     # ==============================================================================
```

## Result

Ran local MLX Parameter Golf in official-like mode on the Mac mini. Final val_bpb=2.3207, val_loss=3.9231, quantized artifact=10373099 bytes. Modified script used. Throughput: 11356 tok/s. Memory: 315MB peak, 315MB active. Score=2.3207. Expected signal: Best case: +1 extra optimizer step and stronger late-training LR utilization, which should beat the current 2.3163 if the run remains stable. Failure mode is mild overshoot in step aggressiveness, but the reserve still keeps a safety margin.
