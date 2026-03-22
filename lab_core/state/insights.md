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

## 2026_03_22_run_0002
- Hypothesis: Re-run sliding-window evaluation once on the official validation split under the 10-minute local cap
- Score: 2.2946
- Outcome: no improvement
- Belief update: Ran local MLX Parameter Golf in official-like mode on the Mac mini. Final val_bpb=2.2946, val_loss=3.8755, quantized artifact=10262767 bytes. Score=2.2946. Expected signal: A second pass with the same sliding-window setup either reproduces roughly the same `val_bpb` and upgrades confidence in the tactic, or regresses enough to mark the prior win as noisy and avoid promoting it.

## 2026_03_22_run_0003
- Hypothesis: Apply one upstream-proven local tactic next: quantization-focused weight decay on the current sliding-window official-split path
- Score: 2.2947
- Outcome: no improvement
- Belief update: Ran local MLX Parameter Golf in official-like mode on the Mac mini. Final val_bpb=2.2947, val_loss=3.8758, quantized artifact=10262012 bytes. Score=2.2947. Expected signal: A modest but real improvement versus 2.29436762, or a clear no-gain result that narrows the next branch before plateau count rises further.

## 2026_03_22_run_0004
- Hypothesis: Research the next upstream tactic to test on the official-split local path: mixed quantization before more exploit runs
- Score: 2.2945
- Outcome: no improvement
- Belief update: Ran local MLX Parameter Golf in official-like mode on the Mac mini. Final val_bpb=2.2945, val_loss=3.8754, quantized artifact=10261283 bytes. Score=2.2945. Expected signal: A concrete, upstream-grounded next run spec that preserves the real code path, official validation split, and 10-minute cap while isolating whether mixed quantization is the next credible improvement lever on M4/16GB.

## 2026_03_22_run_0005
- Hypothesis: Test mixed quantization on the official-split sliding-window path under the 10-minute local cap
- Score: 2.2939
- Outcome: new best
- Belief update: Ran local MLX Parameter Golf in official-like mode on the Mac mini. Final val_bpb=2.2939, val_loss=3.8743, quantized artifact=10262802 bytes. Score=2.2939. Expected signal: A useful exploit run should beat 2.29436762 or fail clearly enough to retire mixed quantization for this local track. Secondary signal: whether mixed quantization preserves artifact safety and wallclock margin on the M4/16GB path without breaking the official-like evaluation procedure.
