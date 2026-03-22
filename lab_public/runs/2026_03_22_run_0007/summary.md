# 2026_03_22_run_0007

## What was tried
Add bigram features to the validated mixed-quantization sliding-window official-split path

## Why it was tried
Recent runs show a live improvement trend, not a plateau: sliding-window eval improved the local best, mixed quantization improved it again, and the follow-up validation passed at 2.29350473. That means the current path is credible and does not call for more research or re-validation first. One concrete next tactic is visible from repeated upstream evidence: bigram features appear in multiple stronger public runs and have not been tested locally yet. The queued community idea about validating top candidates twice is already reflected in the current process and does not justify switching to community mode now.

## Main result
- Score: 2.2940
- Runtime: 180.62s
- Passed: True
- Needs validation: True

## What changed
`parameter_golf` adapter run for mode `exploit`.

## Belief update
Ran local MLX Parameter Golf in official-like mode on the Mac mini. Final val_bpb=2.2940, val_loss=3.8746, quantized artifact=10261581 bytes. Score=2.2940. Expected signal: A real exploit win is a lower official-split val_bpb than 2.29350473 under the same 10-minute wallclock cap, with the upstream code path preserved except for adding bigram features on top of the validated mixed-quantization sliding-window setup.

## What next
A real exploit win is a lower official-split val_bpb than 2.29350473 under the same 10-minute wallclock cap, with the upstream code path preserved except for adding bigram features on top of the validated mixed-quantization sliding-window setup.
