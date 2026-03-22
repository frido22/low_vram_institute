# 2026_03_22_run_0014

## What was tried
Reapply Muon Matrix Weight Decay 0.04 On Top Of The Validated Bigram-Residual Scaffold

## Why it was tried
The last validated replay produced a large jump, so the next move should stay close to that scaffold and add one previously validated upstream-aligned tactic. Matrix weight decay at 0.04 was the best prior quantization-oriented optimizer tweak; 0.03 and 0.05 were flat, so 0.04 is the disciplined exploit point.

## Main result
- Score: 9.2585
- Runtime: 1410.88s
- Passed: True
- Needs validation: True

## Logging focus
- val_bpb
- train_time
- int8_roundtrip

## What changed
`parameter_golf` adapter run for mode `exploit`.

## Belief update
Ran local MLX Parameter Golf in official-like mode on the Mac mini. Final val_bpb=9.2585, val_loss=15.6375, quantized artifact=5051138 bytes. Code patch applied (3 edits). Score=9.2585. Expected signal: If the new scaffold still benefits from quantization-friendly shrinkage, final_int8_zlib_roundtrip_exact val_bpb should improve modestly without destabilizing training throughput or early loss.

## What next
If the new scaffold still benefits from quantization-friendly shrinkage, final_int8_zlib_roundtrip_exact val_bpb should improve modestly without destabilizing training throughput or early loss.
