# 2026_03_22_run_0019

## What was tried
Probe a 3x MLP on the current MLX baseline

## Why it was tried
The loop has plateaued around the tied-embedding residual direction, and upstream records repeatedly pair strong scores with larger MLPs. A single MLP expansion change is a clean research probe that does not relax the official-like setup.

## Main result
- Score: 9.4884
- Runtime: 1514.76s
- Passed: True
- Needs validation: True

## Logging focus
- upstream tactic tested
- score delta
- runtime

## What changed
`parameter_golf` adapter run for mode `research`.

## Belief update
Ran local MLX Parameter Golf in official-like mode on the Mac mini. Final val_bpb=9.4884, val_loss=16.0257, quantized artifact=6241116 bytes. Code patch applied (1 edits). Score=9.4884. Expected signal: If the upstream bigger-MLP pattern transfers to the M4 local track, validation bpb should improve measurably versus the 9.25 baseline path; otherwise this tactic is likely not worth stacking locally without the stronger upstream scaffold.

## What next
If the upstream bigger-MLP pattern transfers to the M4 local track, validation bpb should improve measurably versus the 9.25 baseline path; otherwise this tactic is likely not worth stacking locally without the stronger upstream scaffold.
