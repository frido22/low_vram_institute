# Insights

- No runs yet.

## 2026_03_21_run_0001
- Hypothesis: Establish an upstream-local baseline on M4 under the 10-minute cap
- Score: 2.2944
- Belief update: Ran local MLX Parameter Golf in official-like mode on the Mac mini. Final val_bpb=2.2944, val_loss=3.8753, quantized artifact=10263411 bytes. Score=2.2944. Expected signal: A successful upstream MLX run that completes within 10 minutes on the Mac mini, reports final val_loss/val_bpb on the official validation split, records compressed artifact size, and captures tokens/sec plus peak memory so later changes can be compared against a stable local baseline.

## 2026_03_22_run_0001
- Hypothesis: Apply one upstream-proven local tactic next: sliding-window evaluation on the official validation split
- Score: 2.2944
- Outcome: new best
- Belief update: Ran local MLX Parameter Golf in official-like mode on the Mac mini. Final val_bpb=2.2944, val_loss=3.8751, quantized artifact=10266406 bytes. Score=2.2944. Expected signal: A cleaner lower val_bpb than 2.2944445 from the same upstream-local baseline path, with runtime still inside the 10-minute wallclock cap. Even a modest improvement would confirm the local stack is sensitive to known upstream tactics.
