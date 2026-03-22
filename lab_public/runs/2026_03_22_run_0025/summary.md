# 2026_03_22_run_0025

## What was tried
Replay the Mac-mini warmdown fix exactly once

## Why it was tried
The only clearly improving result was run 2026_03_22_run_0022, and the two follow-up validates did not reapply its code patch. Validate the suspicious win by replaying the same warmdown change before trying new tactics.

## Main result
- Score: 3.3576
- Runtime: 1419.31s
- Passed: True
- Needs validation: False

## Logging focus
- repeatability
- score variance
- validation confidence

## What changed
`parameter_golf` adapter run for mode `validate`.

## Belief update
Ran local MLX Parameter Golf in official-like mode on the Mac mini. Final val_bpb=3.3576, val_loss=5.6709, quantized artifact=7068084 bytes. Code patch applied (1 edits). Score=3.3576. Expected signal: If the gain is real, reapplying the warmdown patch should recover a score near the March 22, 2026 run 2026_03_22_run_0022 result (3.35809913) rather than the unpatched ~9.254 plateau.

## What next
If the gain is real, reapplying the warmdown patch should recover a score near the March 22, 2026 run 2026_03_22_run_0022 result (3.35809913) rather than the unpatched ~9.254 plateau.
