# 2026_03_22_run_0006

## What was tried
Replay Muon WD 0.04 With Momentum 0.99

## Why it was tried
The best score came from the Muon quantization-friendly weight decay line paired with upstream-style Muon momentum 0.99, but the latest result is still marked needs_validation. Plateau count is 0, so the highest-value move is not a new search branch; it is a clean replay of the current best candidate with the exact winning delta and public logging centered on reproducibility and quantized outcome stability.

## Main result
- Score: 9.2505
- Runtime: 1410.33s
- Passed: True
- Needs validation: False

## Logging focus
- reproducibility
- validation_stability
- quantization

## What changed
`parameter_golf` adapter run for mode `validate`.

## Belief update
Ran local MLX Parameter Golf in official-like mode on the Mac mini. Final val_bpb=9.2505, val_loss=15.6240, quantized artifact=5051276 bytes. Code patch applied (4 edits). Score=9.2505. Expected signal: If the gain is real, this replay should land near the 9.2544 band and beat the earlier 9.2585 validation baseline; if it regresses materially, the momentum-0.99 pairing is likely fragile on this hardware.

## What next
If the gain is real, this replay should land near the 9.2544 band and beat the earlier 9.2585 validation baseline; if it regresses materially, the momentum-0.99 pairing is likely fragile on this hardware.
