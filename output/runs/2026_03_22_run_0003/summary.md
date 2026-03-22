# 2026_03_22_run_0003

## What was tried
Validate Muon Matrix Weight Decay 0.04 with a second official-like replay

## Why it was tried
The current best run, 2026_03_22_run_0002 at 9.25997764, is still marked needs_validation. Recent gains came from one isolated upstream-aligned delta, and the public queue explicitly asks to validate top candidates twice before promotion. The right move is to rerun the same matrix-weight-decay patch rather than branch into a new tactic.

## Main result
- Score: 9.2585
- Runtime: 1411.33s
- Passed: True
- Needs validation: False

## Logging focus
- repeatability
- score variance
- validation confidence

## What changed
`parameter_golf` adapter run for mode `validate`.

## Belief update
Ran local MLX Parameter Golf in official-like mode on the Mac mini. Final val_bpb=9.2585, val_loss=15.6375, quantized artifact=5051240 bytes. Code patch applied (2 edits). Score=9.2585. Expected signal: If the gain is real, final_int8_zlib_roundtrip_exact val_bpb should land close to 9.25997764 on a second replay, reducing uncertainty around repeatability and promotion confidence.

## What next
If the gain is real, final_int8_zlib_roundtrip_exact val_bpb should land close to 9.25997764 on a second replay, reducing uncertainty around repeatability and promotion confidence.
