# 2026_03_22_run_0015

## What was tried
Test WD=0.04 alone on the validated 10L int5-MLP + BigramHash(10240) official-split local winner under the 10-minute M4 cap

## Why it was tried
Plateau count is 4, and the last two research runs already showed that adding SWA alone does not help on the current local winner. The combined SWA+WD community reproduction also regressed, so the clean remaining queued upstream delta is weight decay alone. This is a bounded community idea with a clear smell-checked upstream basis and minimal drift from the official path.

## Main result
- Score: 2.2953
- Runtime: 180.98s
- Passed: True
- Needs validation: True

## Logging focus
- official_path_fidelity
- single_delta_isolation
- plateau_break_signal

## What changed
`parameter_golf` adapter run for mode `community`.

## Belief update
Ran local MLX Parameter Golf in official-like mode on the Mac mini. Final val_bpb=2.2953, val_loss=3.8767, quantized artifact=10255742 bytes. Score=2.2953. Expected signal: If WD=0.04 alone improves or matches the best score, it identifies the remaining useful upstream tactic on local hardware; if it regresses again, the current official-best reproduction is likely exhausted on this M4 path and the queue should stop consuming recipe deltas.

## What next
If WD=0.04 alone improves or matches the best score, it identifies the remaining useful upstream tactic on local hardware; if it regresses again, the current official-best reproduction is likely exhausted on this M4 path and the queue should stop consuming recipe deltas.
