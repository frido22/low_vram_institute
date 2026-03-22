# 2026_03_22_run_0012

## What was tried
Test the remaining smell-checked official-best deltas on top of the validated local winner: add SWA start_frac=0.4 and WD=0.04 to the int5-funded 10th-layer plus BigramHash(10240) official-split path under the 10-minute M4 cap

## Why it was tried
One public idea is strong enough to test now: the queued official-best recipe already produced the local best at 2.29234832, and the follow-up validate run passed under the cap, though slightly worse at 2.29388986. Plateau count is only 1, so this is too early for research. The concrete untested deltas from the same upstream tactic bundle are SWA(start_frac=0.4) and WD=0.04, which fit the official code path and avoid repeating the already-tested recipe.

## Main result
- Score: 2.2966
- Runtime: 180.46s
- Passed: True
- Needs validation: True

## Logging focus
- wallclock_vs_cap
- score_delta_vs_best
- artifact_and_recipe_parity

## What changed
`parameter_golf` adapter run for mode `community`.

## Belief update
Ran local MLX Parameter Golf in official-like mode on the Mac mini. Final val_bpb=2.2966, val_loss=3.8790, quantized artifact=10262585 bytes. Score=2.2966. Expected signal: If the community claim transfers locally, this run should beat 2.29234832 or at least match it more consistently; otherwise it will show that SWA(0.4)+WD=0.04 does not survive the M4 official-like constraint.

## What next
If the community claim transfers locally, this run should beat 2.29234832 or at least match it more consistently; otherwise it will show that SWA(0.4)+WD=0.04 does not survive the M4 official-like constraint.
