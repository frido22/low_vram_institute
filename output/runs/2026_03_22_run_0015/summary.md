# 2026_03_22_run_0015

## What was tried
Replay Current Best Tied-Embedding Bigram Residual

## Why it was tried
The last concrete improvement was a large jump to 5.86622822 on the tied-embedding bigram-residual scaffold, and the immediate follow-up exploit regressed badly to 9.25851788. That pattern argues for confirmation, not another branch. A second clean replay of the current best config is the highest-signal next run because it tests whether 2026_03_22_run_0013 is reproducible under the same 600s path before promoting new tweaks on top of it.

## Main result
- Score: 9.2535
- Runtime: 1410.53s
- Passed: True
- Needs validation: False

## Logging focus
- reproducibility
- score_stability
- roundtrip_exactness

## What changed
`parameter_golf` adapter run for mode `validate`.

## Belief update
Ran local MLX Parameter Golf in official-like mode on the Mac mini. Final val_bpb=9.2535, val_loss=15.6291, quantized artifact=5058353 bytes. Score=9.2535. Expected signal: If the best run is real, another no-patch replay should land near 5.87 again and convert the result from promising to credible. If it snaps back toward the 8-9 range, the apparent win was unstable and future search should shift back to research rather than stack more changes.

## What next
If the best run is real, another no-patch replay should land near 5.87 again and convert the result from promising to credible. If it snaps back toward the 8-9 range, the apparent win was unstable and future search should shift back to research rather than stack more changes.
