# 2026_03_22_run_0020

## What was tried
Tighten Mixed-Quantization Passthrough Threshold

## Why it was tried
Plateaued after validating the tied-embedding bigram residual, and the remaining upstream tactic not cleanly exercised on that scaffold is mixed quantization. Prior work only loosened the passthrough threshold and was flat on a weaker setup, so this run should test the opposite direction: force more small float tensors through int8 to trade a modest roundtrip-quality risk for better compressed size.

## Main result
- Score: 9.2520
- Runtime: 1409.51s
- Passed: True
- Needs validation: True

## Logging focus
- serialized_model_int8_zlib
- final_int8_zlib_roundtrip_exact
- val_bpb

## What changed
`parameter_golf` adapter run for mode `research`.

## Belief update
Ran local MLX Parameter Golf in official-like mode on the Mac mini. Final val_bpb=9.2520, val_loss=15.6265, quantized artifact=5058280 bytes. Code patch applied (1 edits). Score=9.2520. Expected signal: `serialized_model_int8_zlib` should drop measurably while `final_int8_zlib_roundtrip_exact val_bpb` stays near the validated 5.86 band; if bpb degrades sharply, the threshold is too aggressive and mixed-quantization needs finer selectivity instead of a global cutoff.

## What next
`serialized_model_int8_zlib` should drop measurably while `final_int8_zlib_roundtrip_exact val_bpb` stays near the validated 5.86 band; if bpb degrades sharply, the threshold is too aggressive and mixed-quantization needs finer selectivity instead of a global cutoff.
