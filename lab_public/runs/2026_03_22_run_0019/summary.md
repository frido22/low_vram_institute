# 2026_03_22_run_0019

## What was tried
Re-run upstream baseline twice under the official 10-minute validation path on M4

## Why it was tried
Recent run 2026_03_22_run_0018 is flat, slightly worse than best, and marked needs_validation. The strongest stable signal is still 2026_03_22_run_0017, so the next step is confirmation rather than new search.

## Main result
- Score: 2.2943
- Runtime: 180.74s
- Passed: True
- Needs validation: False

## Logging focus
- upstream parity
- rerun stability
- time-cap compliance

## What changed
`parameter_golf` adapter run for mode `validate`.

## Belief update
Ran local MLX Parameter Golf in official-like mode on the Mac mini. Final val_bpb=2.2943, val_loss=3.8750, quantized artifact=10259325 bytes. Score=2.2943. Expected signal: Two close scores on the real upstream validation split, same code path, within the 10-minute cap, confirming whether ~2.2933 is stable on the Mac mini M4 despite the hardware mismatch.

## What next
Two close scores on the real upstream validation split, same code path, within the 10-minute cap, confirming whether ~2.2933 is stable on the Mac mini M4 despite the hardware mismatch.
