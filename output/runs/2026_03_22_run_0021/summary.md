# 2026_03_22_run_0021

## What was tried
Probe decoupled weight decay on the current tied-residual MLX path

## Why it was tried
The loop is plateaued, and upstream records repeatedly point to weight decay improving both generalization and post-quantization quality. A previous local Muon-WD test was on a weaker baseline, so the right next step is to retest decoupled weight decay on the current stronger tied-residual regime rather than revisiting flat eval or MLP tweaks.

## Main result
- Score: 9.3116
- Runtime: 1410.17s
- Passed: True
- Needs validation: True

## Logging focus
- upstream tactic tested
- score delta
- quantization effect

## What changed
`parameter_golf` adapter run for mode `research`.

## Belief update
Ran local MLX Parameter Golf in official-like mode on the Mac mini. Final val_bpb=9.3116, val_loss=15.7271, quantized artifact=5050357 bytes. Code patch applied (3 edits). Score=9.3116. Expected signal: If quantization-friendly regularization transfers to this MLX setup, post-roundtrip val_bpb should move back toward the 5.86 band; if it stays flat, weight decay can be deprioritized for the current architecture. Public signal should include exact score delta and whether artifact-friendly shrinkage helped.

## What next
If quantization-friendly regularization transfers to this MLX setup, post-roundtrip val_bpb should move back toward the 5.86 band; if it stays flat, weight decay can be deprioritized for the current architecture. Public signal should include exact score delta and whether artifact-friendly shrinkage helped.
