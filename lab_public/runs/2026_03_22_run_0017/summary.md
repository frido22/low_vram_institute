# 2026_03_22_run_0017

## What was tried
Replay the validated tied-embedding bigram residual once more

## Why it was tried
The current best run 2026_03_22_run_0016 improved to 5.86552997 but is still marked needs_validation. A no-patch replay failed badly in run_0015, so validation should reapply the exact bigram-residual patch that worked in runs 0013 and 0016 rather than testing a new delta.

## Main result
- Score: 5.8671
- Runtime: 1417.16s
- Passed: True
- Needs validation: False

## Logging focus
- repeatability
- score variance
- validation confidence

## What changed
`parameter_golf` adapter run for mode `validate`.

## Belief update
Ran local MLX Parameter Golf in official-like mode on the Mac mini. Final val_bpb=5.8671, val_loss=9.9095, quantized artifact=5057694 bytes. Code patch applied (3 edits). Score=5.8671. Expected signal: A third replay near 5.8655-5.8662 would raise confidence that the bigram-residual gain is real on this Mac mini path; a large regression would indicate hidden instability or patch mismatch.

## What next
A third replay near 5.8655-5.8662 would raise confidence that the bigram-residual gain is real on this Mac mini path; a large regression would indicate hidden instability or patch mismatch.
