# 2026_03_22_run_0026

## What was tried
Add validated tied-embedding bigram residual on top of the Mac-mini warmdown fix

## Why it was tried
The last two real improvements came from a Mac-specific warmdown correction, while earlier validated runs showed the tied-embedding bigram residual was the strongest architectural win before that. The clean next exploit is to combine those two already-positive signals and keep the warmdown fix in place, instead of probing another unvalidated tactic.

## Main result
- Score: 3.4250
- Runtime: 1424.93s
- Passed: True
- Needs validation: True

## Logging focus
- val_bpb
- wallclock_budget
- train_dynamics

## What changed
`parameter_golf` adapter run for mode `exploit`.

## Belief update
Ran local MLX Parameter Golf in official-like mode on the Mac mini. Final val_bpb=3.4250, val_loss=5.7848, quantized artifact=6819892 bytes. Code patch applied (4 edits). Score=3.4250. Expected signal: If the gains are complementary, final_int8_zlib_roundtrip_exact val_bpb should beat 3.35758715. If the interaction is bad, it likely regresses toward the older bigram-only regime or stays near the current best.

## What next
If the gains are complementary, final_int8_zlib_roundtrip_exact val_bpb should beat 3.35758715. If the interaction is bad, it likely regresses toward the older bigram-only regime or stays near the current best.
