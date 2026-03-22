# 2026_03_22_run_0013

## What was tried
Isolate the next untested upstream tactic on top of the validated 10L int5-MLP + BigramHash(10240) local winner before more exploit runs

## Why it was tried
Plateau count is 2, and the last bounded add-on test regressed: run 0012 scored 2.2966215 after adding SWA(start_frac=0.4) and WD=0.04 on top of the current winner, while the best remains 2.29234832 from run 0010 and already received one confirmation pass in run 0011 at 2.29388986. The obvious queued community recipe has now been substantially exercised, so the next step should be to research one genuinely untested upstream tactic rather than repeat community deltas or stack more changes blindly.

## Main result
- Score: 2.2941
- Runtime: 180.61s
- Passed: True
- Needs validation: True

## Logging focus
- plateau handling
- untested upstream tactics
- next-run selection discipline

## What changed
`parameter_golf` adapter run for mode `research`.

## Belief update
Ran local MLX Parameter Golf in official-like mode on the Mac mini. Final val_bpb=2.2941, val_loss=3.8746, quantized artifact=10259955 bytes. Score=2.2941. Expected signal: A short ranked candidate list with one concrete next run that is upstream-adjacent, not already tested by title, and plausibly compatible with the official-like M4 10-minute path.

## What next
A short ranked candidate list with one concrete next run that is upstream-adjacent, not already tested by title, and plausibly compatible with the official-like M4 10-minute path.
