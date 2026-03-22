# 2026_03_22_run_0002

## What was tried
Re-run sliding-window evaluation once on the official validation split under the 10-minute local cap

## Why it was tried
The latest run is a new best and is already flagged `needs_validation=true`. Plateau count is 0, so this is not a research turn. One concrete tactic is already in play, but before stacking more changes, the clean next step is to check whether the gain from sliding-window eval is stable on the same upstream-like path, validation split, and wallclock budget. The queued community suggestion aligns with standard noise control and passes a basic smell check, but this should be treated as a validation step rather than a community-led experiment.

## Main result
- Score: 2.2946
- Runtime: 180.49s
- Passed: True
- Needs validation: False

## What changed
`parameter_golf` adapter run for mode `validate`.

## Belief update
Ran local MLX Parameter Golf in official-like mode on the Mac mini. Final val_bpb=2.2946, val_loss=3.8755, quantized artifact=10262767 bytes. Score=2.2946. Expected signal: A second pass with the same sliding-window setup either reproduces roughly the same `val_bpb` and upgrades confidence in the tactic, or regresses enough to mark the prior win as noisy and avoid promoting it.

## What next
A second pass with the same sliding-window setup either reproduces roughly the same `val_bpb` and upgrades confidence in the tactic, or regresses enough to mark the prior win as noisy and avoid promoting it.
