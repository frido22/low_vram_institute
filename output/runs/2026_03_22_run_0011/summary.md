# 2026_03_22_run_0011

## What was tried
Probe Lower Muon Matrix Weight Decay At 0.03

## Why it was tried
The best validated result came from Muon matrix weight decay at 0.04 with momentum 0.99, while a push to 0.05 was flat-to-worse and mixed-quantization threshold tweaks also plateaued. After four flat runs, the cleanest upstream-aligned next step is to map the weight-decay slope downward with a single delta, keeping the validated optimizer scaffold intact.

## Main result
- Score: 9.2528
- Runtime: 1410.01s
- Passed: True
- Needs validation: True

## Logging focus
- val_bpb_stability
- quantized_roundtrip_bpb
- wallclock_budget_usage

## What changed
`parameter_golf` adapter run for mode `research`.

## Belief update
Ran local MLX Parameter Golf in official-like mode on the Mac mini. Final val_bpb=9.2528, val_loss=15.6278, quantized artifact=5053083 bytes. Code patch applied (2 edits). Score=9.2528. Expected signal: If 0.04 was slightly over-regularizing under the 600s M4 regime, 0.03 should improve final_int8_zlib_roundtrip_exact val_bpb modestly; otherwise it should come back flat and narrow the local optimum around 0.04.

## What next
If 0.04 was slightly over-regularizing under the 600s M4 regime, 0.03 should improve final_int8_zlib_roundtrip_exact val_bpb modestly; otherwise it should come back flat and narrow the local optimum around 0.04.
