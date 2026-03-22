# 2026_03_22_run_0004

## What was tried
Research the next upstream tactic to test on the official-split local path: mixed quantization before more exploit runs

## Why it was tried
Plateau count is 2 and the last exploit run regressed from the current best (2.29474478 vs 2.29436762), so another immediate exploit is weakly justified. The best recent gain came from sliding-window eval, and the next repeatedly seen upstream tactic not yet tested in local runs is mixed quantization. Validate is lower priority because the current best already has one official-split rerun nearby (2.29455078), which looks like noise rather than a suspicious win. Community mode is not the right next step because the queued idea is process policy, not the highest-value experiment under the current plateau.

## Main result
- Score: 2.2945
- Runtime: 180.46s
- Passed: True
- Needs validation: True

## What changed
`parameter_golf` adapter run for mode `research`.

## Belief update
Ran local MLX Parameter Golf in official-like mode on the Mac mini. Final val_bpb=2.2945, val_loss=3.8754, quantized artifact=10261283 bytes. Score=2.2945. Expected signal: A concrete, upstream-grounded next run spec that preserves the real code path, official validation split, and 10-minute cap while isolating whether mixed quantization is the next credible improvement lever on M4/16GB.

## What next
A concrete, upstream-grounded next run spec that preserves the real code path, official validation split, and 10-minute cap while isolating whether mixed quantization is the next credible improvement lever on M4/16GB.
