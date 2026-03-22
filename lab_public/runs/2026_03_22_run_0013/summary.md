# 2026_03_22_run_0013

## What was tried
Replay Tied-Embedding Bigram Residual

## Why it was tried
Run 0012 produced a large step-change over the prior 9.25 plateau, and the queue explicitly says to validate top candidates twice before promotion. The safest next move is to replay the same upstream-aligned bigram feature idea, not branch into a fresh variant yet.

## Main result
- Score: 5.8662
- Runtime: 1417.40s
- Passed: True
- Needs validation: False

## Logging focus
- validation_replay
- score_stability
- artifact_size

## What changed
`parameter_golf` adapter run for mode `validate`.

## Belief update
Ran local MLX Parameter Golf in official-like mode on the Mac mini. Final val_bpb=5.8662, val_loss=9.9080, quantized artifact=5057771 bytes. Code patch applied (3 edits). Score=5.8662. Expected signal: A second run with the tied-embedding bigram residual should stay near the 8.0682 result if the gain is real; a snapback toward the 9.25 band would mark the prior improvement as unstable.

## What next
A second run with the tied-embedding bigram residual should stay near the 8.0682 result if the gain is real; a snapback toward the 9.25 band would mark the prior improvement as unstable.
