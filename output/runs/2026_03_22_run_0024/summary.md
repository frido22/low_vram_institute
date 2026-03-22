# 2026_03_22_run_0024

## What was tried
Replay Warmdown-Tuned MLX Path

## Why it was tried
Run 2026_03_22_run_0022 produced a large unexplained gain after shortening warmdown, but the immediate replay on March 22, 2026 was flat. The highest-value next step is to validate whether the warmdown-tuned schedule is a real win on this Mac mini or a one-off timing artifact. The current script already matches that tuned path, so the correct experiment is an exact replay with no further code changes.

## Main result
- Score: 9.2541
- Runtime: 1410.10s
- Passed: True
- Needs validation: False

## Logging focus
- wallclock_usage
- validation_stability
- throughput

## What changed
`parameter_golf` adapter run for mode `validate`.

## Belief update
Ran local MLX Parameter Golf in official-like mode on the Mac mini. Final val_bpb=9.2541, val_loss=15.6299, quantized artifact=5058344 bytes. Score=9.2541. Expected signal: A second low val_bpb near 3.35809913 would promote the warmdown change from suspicious win to validated tactic. Another result near 9.25 on March 22, 2026 would strongly suggest the prior win was unstable or wallclock-sensitive.

## What next
A second low val_bpb near 3.35809913 would promote the warmdown change from suspicious win to validated tactic. Another result near 9.25 on March 22, 2026 would strongly suggest the prior win was unstable or wallclock-sensitive.
