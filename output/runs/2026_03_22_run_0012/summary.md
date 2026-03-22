# 2026_03_22_run_0012

## What was tried
Probe Tied-Embedding Bigram Residual

## Why it was tried
Plateaued Muon and mixed-quantization sweeps are flat, while upstream bigram features remain untested in this MLX path. Add one cheap scalar-gated previous-token embedding residual so the model can capture local token transitions with negligible parameter and serialization cost.

## Main result
- Score: 8.0682
- Runtime: 1440.76s
- Passed: True
- Needs validation: True

## Logging focus
- val_bpb
- train_time_ms
- serialized_model_int8_zlib

## What changed
`parameter_golf` adapter run for mode `research`.

## Belief update
Ran local MLX Parameter Golf in official-like mode on the Mac mini. Final val_bpb=8.0682, val_loss=13.6270, quantized artifact=5061003 bytes. Code patch applied (5 edits). Score=8.0682. Expected signal: If upstream-style bigram locality helps here, final val_bpb should improve beyond the 9.2505 plateau without materially increasing train step time or int8_zlib size; otherwise this likely comes back flat and we can drop the idea.

## What next
If upstream-style bigram locality helps here, final val_bpb should improve beyond the 9.2505 plateau without materially increasing train step time or int8_zlib size; otherwise this likely comes back flat and we can drop the idea.
