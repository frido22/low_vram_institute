# 2026_03_22_run_0002

## What was tried
Reapply Muon Matrix Weight Decay 0.04

## Why it was tried
The only recorded improvement came from Muon weight decay 0.04, and upstream tactics explicitly call out weight decay for quantization. With plateau_count still at 0, the highest-leverage move is to replay that winning delta directly in the MLX path rather than branching into a new idea.

## Main result
- Score: 9.2600
- Runtime: 1412.08s
- Passed: True
- Needs validation: True

## Logging focus
- score
- repeatability
- quantization

## What changed
`parameter_golf` adapter run for mode `exploit`.

## Belief update
Ran local MLX Parameter Golf in official-like mode on the Mac mini. Final val_bpb=9.2600, val_loss=15.6399, quantized artifact=5051318 bytes. Code patch applied (2 edits). Score=9.2600. Expected signal: If the prior win was real, final_int8_zlib_roundtrip_exact val_bpb should match or beat 9.26395018. A repeat improvement would justify promotion to validation mode next.

## What next
If the prior win was real, final_int8_zlib_roundtrip_exact val_bpb should match or beat 9.26395018. A repeat improvement would justify promotion to validation mode next.
