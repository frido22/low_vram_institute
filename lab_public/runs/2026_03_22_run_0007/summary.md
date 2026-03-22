# 2026_03_22_run_0007

## What was tried
Replay validated Muon WD 0.04 + momentum 0.99, then tighten mixed-quantization passthrough

## Why it was tried
The strongest validated direction is Muon matrix weight decay 0.04 with momentum 0.99. The next low-risk exploit is to keep that optimizer recipe and make one upstream-inspired compression delta: reduce the fp16 passthrough budget so more tensors go through int8, which should improve serialized size if roundtrip loss stays flat.

## Main result
- Score: 9.2533
- Runtime: 1410.30s
- Passed: True
- Needs validation: True

## Logging focus
- val_bpb
- serialized_model_int8_zlib
- final_int8_zlib_roundtrip_exact

## What changed
`parameter_golf` adapter run for mode `exploit`.

## Belief update
Ran local MLX Parameter Golf in official-like mode on the Mac mini. Final val_bpb=9.2533, val_loss=15.6287, quantized artifact=5051208 bytes. Code patch applied (3 edits). Score=9.2533. Expected signal: If this mixed-quantization tweak is good, final_int8_zlib_roundtrip_exact val_bpb should stay near the validated Muon baseline while the int8 payload and compressed artifact shrink measurably.

## What next
If this mixed-quantization tweak is good, final_int8_zlib_roundtrip_exact val_bpb should stay near the validated Muon baseline while the int8 payload and compressed artifact shrink measurably.
