# 2026_03_22_run_0003

## What was tried
Apply one upstream-proven local tactic next: quantization-focused weight decay on the current sliding-window official-split path

## Why it was tried
The latest validation run passed but did not beat the best score, so there is no suspicious win to re-check. Plateau count is only 1, which is too early to switch into broader research. One concrete upstream tactic is already visible: weight decay for quantization appears repeatedly in top runs and is a smaller, cleaner next change than introducing bigram features or mixed quantization. It preserves the real upstream code path, the official validation split, and the 10-minute cap while testing a likely high-signal optimization on top of the current best local setup.

## Main result
- Score: 2.2947
- Runtime: 180.54s
- Passed: True
- Needs validation: True

## What changed
`parameter_golf` adapter run for mode `exploit`.

## Belief update
Ran local MLX Parameter Golf in official-like mode on the Mac mini. Final val_bpb=2.2947, val_loss=3.8758, quantized artifact=10262012 bytes. Score=2.2947. Expected signal: A modest but real improvement versus 2.29436762, or a clear no-gain result that narrows the next branch before plateau count rises further.

## What next
A modest but real improvement versus 2.29436762, or a clear no-gain result that narrows the next branch before plateau count rises further.
