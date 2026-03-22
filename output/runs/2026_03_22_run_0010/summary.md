# 2026_03_22_run_0010

## What was tried
Probe Muon Matrix Weight Decay 0.05 Around The Validated 0.99 Momentum Scaffold

## Why it was tried
Plateau count is 3, so this should be a research run rather than another mixed-quantization threshold replay. The strongest stable signal so far came from Muon matrix weight decay with momentum 0.99, while recent passthrough-threshold tweaks were flat. The next clean upstream-inspired move is to stay on the quantization-friendly weight-decay axis and test a small neighborhood step from the validated 0.04 setting to 0.05, keeping the validated momentum replay in place.

## Main result
- Score: 9.2551
- Runtime: 1410.40s
- Passed: True
- Needs validation: True

## Logging focus
- muon_weight_decay
- quantized_roundtrip_bpb
- wallclock_usage

## What changed
`parameter_golf` adapter run for mode `research`.

## Belief update
Ran local MLX Parameter Golf in official-like mode on the Mac mini. Final val_bpb=9.2551, val_loss=15.6317, quantized artifact=5049714 bytes. Code patch applied (2 edits). Score=9.2551. Expected signal: If the weight-decay-for-quantization effect is still under-tuned, 0.05 should improve final_int8_zlib_roundtrip_exact slightly or at least clarify whether the optimum is above 0.04. A flat or worse result would narrow the local search and argue for leaving the WD axis.

## What next
If the weight-decay-for-quantization effect is still under-tuned, 0.05 should improve final_int8_zlib_roundtrip_exact slightly or at least clarify whether the optimum is above 0.04. A flat or worse result would narrow the local search and argue for leaving the WD axis.
