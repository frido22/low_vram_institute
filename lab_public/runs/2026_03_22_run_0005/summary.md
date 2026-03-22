# 2026_03_22_run_0005

## What was tried
Test mixed quantization on the official-split sliding-window path under the 10-minute local cap

## Why it was tried
Plateau count is 3, but the last run was already a research pass and it surfaced one concrete upstream tactic: mixed quantization. Recent evidence says sliding-window eval is the only local tactic here that improved the best score (2.29436762), while the follow-up weight-decay exploit regressed and the validation rerun did not expose a fake win. The clean next move is to keep the real upstream code path, official validation split, and 10-minute cap fixed, and change only quantization layout on top of the current best sliding-window setup.

## Main result
- Score: 2.2939
- Runtime: 180.47s
- Passed: True
- Needs validation: True

## What changed
`parameter_golf` adapter run for mode `exploit`.

## Belief update
Ran local MLX Parameter Golf in official-like mode on the Mac mini. Final val_bpb=2.2939, val_loss=3.8743, quantized artifact=10262802 bytes. Score=2.2939. Expected signal: A useful exploit run should beat 2.29436762 or fail clearly enough to retire mixed quantization for this local track. Secondary signal: whether mixed quantization preserves artifact safety and wallclock margin on the M4/16GB path without breaking the official-like evaluation procedure.

## What next
A useful exploit run should beat 2.29436762 or fail clearly enough to retire mixed quantization for this local track. Secondary signal: whether mixed quantization preserves artifact safety and wallclock margin on the M4/16GB path without breaking the official-like evaluation procedure.
