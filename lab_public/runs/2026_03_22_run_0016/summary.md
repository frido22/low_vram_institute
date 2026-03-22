# 2026_03_22_run_0016

## What was tried
Establish Official Parameter Golf Baseline on M4 Mac mini

## Why it was tried
No prior runs exist, so the highest-value step is to reproduce the upstream baseline as faithfully as possible on local hardware. This tests the real code path, official validation split, and 10-minute cap before any adaptation, while isolating the intentional hardware mismatch.

## Main result
- Score: 2.2965
- Runtime: 180.22s
- Passed: True
- Needs validation: True

## Logging focus
- upstream parity
- 10-minute cap compliance
- reproducible baseline capture

## What changed
`parameter_golf` adapter run for mode `explore`.

## Belief update
Ran local MLX Parameter Golf in official-like mode on the Mac mini. Final val_bpb=2.2965, val_loss=3.8787, quantized artifact=10267272 bytes. Score=2.2965. Expected signal: A clean first score plus timing/memory traces that show whether the official procedure fits within 10 minutes on 16GB Apple Silicon and is stable enough to use as the reference baseline.

## What next
A clean first score plus timing/memory traces that show whether the official procedure fits within 10 minutes on 16GB Apple Silicon and is stable enough to use as the reference baseline.
