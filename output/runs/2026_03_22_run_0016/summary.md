# 2026_03_22_run_0016

## What was tried
Community Replay Of The Validated Tied-Embedding Bigram Residual

## Why it was tried
The queue’s strongest actionable suggestion is to validate top candidates twice before promotion. The best local result came from the tied-embedding bigram residual patch, while subsequent deviations were flat, so the clean next run is an exact replay of that winning patch to measure repeatability rather than stacking another tactic.

## Main result
- Score: 5.8655
- Runtime: 1415.57s
- Passed: True
- Needs validation: True

## Logging focus
- community idea outcome
- repeatability
- validation confidence

## What changed
`parameter_golf` adapter run for mode `community`.

## Belief update
Ran local MLX Parameter Golf in official-like mode on the Mac mini. Final val_bpb=5.8655, val_loss=9.9068, quantized artifact=5057665 bytes. Code patch applied (3 edits). Score=5.8655. Expected signal: A second confirmation run for the bigram-residual scaffold should show whether the 2026-03-22 improvement is stable or a one-off, and clarify if this path deserves continued exploitation.

## What next
A second confirmation run for the bigram-residual scaffold should show whether the 2026-03-22 improvement is stable or a one-off, and clarify if this path deserves continued exploitation.
