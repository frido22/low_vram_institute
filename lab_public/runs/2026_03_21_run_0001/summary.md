# 2026_03_21_run_0001

## What was tried
Establish an upstream-local baseline on M4 under the 10-minute cap

## Why it was tried
There is no local baseline yet. The highest-value next step is to run the official Apple Silicon path with the official cached FineWeb validation split, preserve the 10-minute wallclock constraint, and measure what the M4/16GB hardware can actually sustain. That gives a defensible reference before testing any architectural or process changes.

## Main result
- Score: 2.2944
- Runtime: 180.42s
- Passed: True
- Needs validation: True

## What changed
`parameter_golf` adapter run for mode `explore`.

## Belief update
Ran local MLX Parameter Golf in official-like mode on the Mac mini. Final val_bpb=2.2944, val_loss=3.8753, quantized artifact=10263411 bytes. Score=2.2944. Expected signal: A successful upstream MLX run that completes within 10 minutes on the Mac mini, reports final val_loss/val_bpb on the official validation split, records compressed artifact size, and captures tokens/sec plus peak memory so later changes can be compared against a stable local baseline.

## What next
A successful upstream MLX run that completes within 10 minutes on the Mac mini, reports final val_loss/val_bpb on the official validation split, records compressed artifact size, and captures tokens/sec plus peak memory so later changes can be compared against a stable local baseline.
