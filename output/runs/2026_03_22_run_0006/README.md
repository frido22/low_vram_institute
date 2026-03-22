# Faster Muon Orthogonalization While Preserving the Best Eval Path

**Score:** 2.373343 val_bpb
**Hardware:** Apple Silicon Mac mini M4 16GB (600s wallclock cap; step count depends on the script)
**Runtime:** 207s

## Approach

The best local run is still the near-baseline exploit, while recent schedule-only changes regressed. That points away from spending another run on LR timing and toward buying more real optimizer updates inside the same 600s budget. The failed Adam-matrix run suggests removing Muon is too destructive, so this patch keeps the current best training/eval/quantization stack and only shortens Muon's Newton-Schulz backend from 5 steps to 3. This is a speed-first optimizer change, aligned with the open community speed suggestion, but it stays close to the current winner instead of pivoting to a new architecture.

## Changes

```diff
--- a/train_gpt_mlx.py
+++ b/train_gpt_mlx.py
@@ -85,7 +85,7 @@
     matrix_lr: float = float(os.environ.get("MATRIX_LR", 0.02))
     scalar_lr: float = float(os.environ.get("SCALAR_LR", 0.02))
     muon_momentum: float = float(os.environ.get("MUON_MOMENTUM", 0.95))
-    muon_backend_steps: int = int(os.environ.get("MUON_BACKEND_STEPS", 5))
+    muon_backend_steps: int = int(os.environ.get("MUON_BACKEND_STEPS", 3))
     muon_momentum_warmup_start: float = float(os.environ.get("MUON_MOMENTUM_WARMUP_START", 0.85))
     muon_momentum_warmup_steps: int = int(os.environ.get("MUON_MOMENTUM_WARMUP_STEPS", 500))
     grad_clip_norm: float = float(os.environ.get("GRAD_CLIP_NORM", 0.0))
```

## Result

Ran local MLX Parameter Golf in official-like mode on the Mac mini. Final val_bpb=2.3733, val_loss=4.0121, quantized artifact=8964863 bytes. Modified script used. Throughput: 11869 tok/s. Memory: 312MB peak, 312MB active. Score=2.3733. Expected signal: Lower `step_avg` and higher `tok_s`, ideally yielding 1-3 extra training steps within 600s with similar update quality; success looks like flat or better final `val_bpb` plus a visible throughput gain.
