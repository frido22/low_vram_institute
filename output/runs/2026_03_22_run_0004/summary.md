# 2026_03_22_run_0004

## What was tried
Add Quantization-Friendly Weight Decay To Tied Embeddings

## Why it was tried
Muon matrix weight decay 0.04 has now improved twice and passed validation. The next narrow exploit is to extend the same quantization-oriented regularization to the largest and most score-sensitive tensor: the tied embedding matrix that is also reused as the LM head during final int8 roundtrip eval. This keeps the delta isolated, follows the upstream weight-decay-for-quantization theme, and avoids mixing in architecture or eval changes before there is a plateau.

## Main result
- Score: 9.6870
- Runtime: 1409.88s
- Passed: True
- Needs validation: True

## Logging focus
- quantization_fidelity
- optimizer_behavior
- reproducibility

## What changed
`parameter_golf` adapter run for mode `exploit`.

## Belief update
Ran local MLX Parameter Golf in official-like mode on the Mac mini. Final val_bpb=9.6870, val_loss=16.3612, quantized artifact=5031726 bytes. Code patch applied (3 edits). Score=9.6870. Expected signal: If this direction is real, final_int8_zlib_roundtrip_exact val_bpb should improve slightly at similar training loss, with any size impact coming only from cleaner embedding weights rather than broader quantization changes.

## What next
If this direction is real, final_int8_zlib_roundtrip_exact val_bpb should improve slightly at similar training loss, with any size impact coming only from cleaner embedding weights rather than broader quantization changes.
