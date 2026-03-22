# 2026_03_22_run_0008

## What was tried
Test SWA start_frac=0.4 on the validated mixed-quantization sliding-window official-split path

## Why it was tried
The current best is already validated at 2.29350473 on the official-like path, and the latest exploit adding bigram features regressed to 2.2940162. Plateau count is only 1, so this is not a research reset yet. A single concrete next tactic is visible from upstream/public evidence: narrower late-phase SWA repeatedly appears in strong runs and has not been tested locally, while keeping the same upstream code path, official validation split, and 10-minute wallclock cap.

## Main result
- Score: 2.2956
- Runtime: 180.67s
- Passed: True
- Needs validation: True

## What changed
`parameter_golf` adapter run for mode `exploit`.

## Belief update
Ran local MLX Parameter Golf in official-like mode on the Mac mini. Final val_bpb=2.2956, val_loss=3.8773, quantized artifact=10260347 bytes. Score=2.2956. Expected signal: A modest improvement over 2.29350473 or a clear no-gain result that lets the lab deprioritize SWA tuning before spending more cycles on larger architecture changes.

## What next
A modest improvement over 2.29350473 or a clear no-gain result that lets the lab deprioritize SWA tuning before spending more cycles on larger architecture changes.
