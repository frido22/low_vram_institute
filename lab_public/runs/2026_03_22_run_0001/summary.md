# 2026_03_22_run_0001

## What was tried
Apply one upstream-proven local tactic next: sliding-window evaluation on the official validation split

## Why it was tried
There is only one completed run, it passed, and plateau_count is 0, so this is too early for research or community testing. The clearest next move is exploit: keep the upstream code path and 10-minute cap, change one tactic with repeated upstream evidence, and measure on the official validation split. Sliding-window eval is attractive because it is repeatedly present in strong upstream runs and should transfer to the M4 local setup without changing hardware assumptions or drifting far from the official procedure.

## Main result
- Score: 2.2944
- Runtime: 180.26s
- Passed: True
- Needs validation: True

## What changed
`parameter_golf` adapter run for mode `exploit`.

## Belief update
Ran local MLX Parameter Golf in official-like mode on the Mac mini. Final val_bpb=2.2944, val_loss=3.8751, quantized artifact=10266406 bytes. Score=2.2944. Expected signal: A cleaner lower val_bpb than 2.2944445 from the same upstream-local baseline path, with runtime still inside the 10-minute wallclock cap. Even a modest improvement would confirm the local stack is sensitive to known upstream tactics.

## What next
A cleaner lower val_bpb than 2.2944445 from the same upstream-local baseline path, with runtime still inside the 10-minute wallclock cap. Even a modest improvement would confirm the local stack is sensitive to known upstream tactics.
