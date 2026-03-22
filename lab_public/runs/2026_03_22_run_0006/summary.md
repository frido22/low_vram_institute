# 2026_03_22_run_0006

## What was tried
Re-run the mixed-quantization sliding-window official-split path once to confirm the new local best under the 10-minute cap

## Why it was tried
The latest run, 2026_03_22_run_0005, is the current best at 2.29386796 and is still marked `needs_validation=true`. Plateau count is 0, so there is no reason to switch into research. A concrete next tactic is not the priority yet because the best score came from a fresh exploit and should be checked for noise before promotion. This also aligns with the queued community suggestion to validate top candidates twice, but the justification already stands on recent run state alone.

## Main result
- Score: 2.2935
- Runtime: 180.53s
- Passed: True
- Needs validation: False

## What changed
`parameter_golf` adapter run for mode `validate`.

## Belief update
Ran local MLX Parameter Golf in official-like mode on the Mac mini. Final val_bpb=2.2935, val_loss=3.8737, quantized artifact=10261883 bytes. Score=2.2935. Expected signal: If the rerun stays near 2.29386796 on the same upstream-like path and within the 10-minute wallclock cap, mixed quantization becomes a trusted baseline to exploit from next. If it regresses materially, treat the prior score as noisy and avoid compounding on an unstable win.

## What next
If the rerun stays near 2.29386796 on the same upstream-like path and within the 10-minute wallclock cap, mixed quantization becomes a trusted baseline to exploit from next. If it regresses materially, treat the prior score as noisy and avoid compounding on an unstable win.
