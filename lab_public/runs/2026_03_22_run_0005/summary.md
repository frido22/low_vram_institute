# 2026_03_22_run_0005

## What was tried
Pair validated Muon WD 0.04 with upstream Muon momentum 0.99

## Why it was tried
The only local change that has improved and validated is Muon-side matrix weight decay at 0.04. Extending decay to tied embeddings regressed badly, so the next exploit should stay on the same optimizer path and add one upstream-aligned knob from stronger records: higher Muon momentum.

## Main result
- Score: 9.2544
- Runtime: 1410.08s
- Passed: True
- Needs validation: True

## Logging focus
- score delta
- optimizer behavior
- wallclock

## What changed
`parameter_golf` adapter run for mode `exploit`.

## Belief update
Ran local MLX Parameter Golf in official-like mode on the Mac mini. Final val_bpb=9.2544, val_loss=15.6305, quantized artifact=5051281 bytes. Code patch applied (3 edits). Score=9.2544. Expected signal: If the current best path is still underpowered in the first ~15 optimizer steps, raising Muon momentum from 0.95 to 0.99 while keeping matrix-only WD=0.04 should improve final_int8_zlib_roundtrip_exact val_bpb without changing runtime or artifact behavior much.

## What next
If the current best path is still underpowered in the first ~15 optimizer steps, raising Muon momentum from 0.95 to 0.99 while keeping matrix-only WD=0.04 should improve final_int8_zlib_roundtrip_exact val_bpb without changing runtime or artifact behavior much.
