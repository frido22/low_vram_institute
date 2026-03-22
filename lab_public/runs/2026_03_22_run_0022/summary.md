# 2026_03_22_run_0022

## What was tried
Shorten warmdown to match the Mac mini's actual 10-minute step budget

## Why it was tried
The loop is plateaued, recent upstream-style probes were flat, and the local M4 path only completes about 15 training steps in 600 seconds. With `warmdown_iters=1200`, the wallclock scheduler is effectively decaying learning rate from the first step on this hardware, so the cleanest next experiment is one explicit schedule fix rather than another architecture or quantization branch.

## Main result
- Score: 3.3581
- Runtime: 1418.49s
- Passed: True
- Needs validation: True

## Logging focus
- wallclock-aligned warmdown
- score delta
- steps completed

## What changed
`parameter_golf` adapter run for mode `research`.

## Belief update
Ran local MLX Parameter Golf in official-like mode on the Mac mini. Final val_bpb=3.3581, val_loss=5.6718, quantized artifact=7068828 bytes. Code patch applied (1 edits). Score=3.3581. Expected signal: If wallclock-aligned warmdown is the hidden bottleneck, reducing `warmdown_iters` to the observed step budget should beat the current 5.8655-5.8671 band or at least improve early-train progress before final roundtrip eval. If it regresses sharply, the validated bigram-residual path depends on the existing ultra-conservative decay and future search should return to upstream tactics instead of more scheduler changes.

## What next
If wallclock-aligned warmdown is the hidden bottleneck, reducing `warmdown_iters` to the observed step budget should beat the current 5.8655-5.8671 band or at least improve early-train progress before final roundtrip eval. If it regresses sharply, the validated bigram-residual path depends on the existing ultra-conservative decay and future search should return to upstream tactics instead of more scheduler changes.
