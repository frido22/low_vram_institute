# 2026_03_22_run_0009

## What was tried
Loosen Mixed-Quantization Passthrough Threshold

## Why it was tried
The validated Muon weight-decay plus momentum line appears near a short plateau, and the last mixed-quantization move tightened passthrough without improving score. Upstream mixed quantization is still the cleanest unexplored lever here, so test the opposite direction: keep slightly larger medium tensors in float to preserve post-roundtrip quality and see whether the compression hit is offset by a better exact final eval.

## Main result
- Score: 9.2515
- Runtime: 1409.83s
- Passed: True
- Needs validation: True

## Logging focus
- quantization_tradeoff
- roundtrip_exact
- artifact_size

## What changed
`parameter_golf` adapter run for mode `research`.

## Belief update
Ran local MLX Parameter Golf in official-like mode on the Mac mini. Final val_bpb=9.2515, val_loss=15.6257, quantized artifact=5058443 bytes. Code patch applied (1 edits). Score=9.2515. Expected signal: If this tradeoff is favorable, final_int8_zlib_roundtrip_exact val_bpb should improve enough to outweigh the modest artifact-size increase; if not, compressed bytes will rise with little or no score gain.

## What next
If this tradeoff is favorable, final_int8_zlib_roundtrip_exact val_bpb should improve enough to outweigh the modest artifact-size increase; if not, compressed bytes will rise with little or no score gain.
