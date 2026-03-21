# 2026_03_21_run_0009

## What was tried
Exploit local MLX by tightening around the current stable recipe and promoting only repeatable gains

## Why it was tried
The lab is on an Apple Silicon MLX track, and repeated community-mode trials have flatlined at 0.61 across runs 0002-0008. That means the immediate bottleneck is not idea intake but disciplined local iteration around a known-good configuration. The next best plan is to exploit: keep the current recipe, run a narrow local sweep over a few high-leverage knobs that are plausible on an M4/16GB setup, and require repeat confirmation before treating any delta as real. Focus on MLX-feasible changes such as batch tokens, sequence length, learning rate/warmdown, validation cadence, and artifact/quantization settings already compatible with the local path rather than architecture changes that assume remote GPU throughput.

## Main result
- Score: 2.3134
- Runtime: 184.24s
- Passed: True
- Needs validation: True

## What changed
`parameter_golf` adapter run for mode `exploit`.

## Belief update
Ran local MLX Parameter Golf proxy on the Mac mini track. Final val_bpb=2.3134, val_loss=3.9073, quantized artifact=8092165 bytes. Score=2.3134. Expected signal: A real improvement would appear as a small but repeatable score increase over 0.61 across at least two local MLX reruns of the same candidate; otherwise the signal is that current variance dominates and the search space should stay narrow.

## What next
A real improvement would appear as a small but repeatable score increase over 0.61 across at least two local MLX reruns of the same candidate; otherwise the signal is that current variance dominates and the search space should stay narrow.
