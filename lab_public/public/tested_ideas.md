# Tested Ideas

- Re-run the mixed-quantization sliding-window official-split path once to confirm the new local best under the 10-minute cap -> 2026_03_22_run_0006 scored 2.2935
- Test mixed quantization on the official-split sliding-window path under the 10-minute local cap -> 2026_03_22_run_0005 scored 2.2939
- Apply one upstream-proven local tactic next: sliding-window evaluation on the official validation split -> 2026_03_22_run_0001 scored 2.2944
- Establish an upstream-local baseline on M4 under the 10-minute cap -> 2026_03_21_run_0001 scored 2.2944
- Research the next upstream tactic to test on the official-split local path: mixed quantization before more exploit runs -> 2026_03_22_run_0004 scored 2.2945
- Re-run sliding-window evaluation once on the official validation split under the 10-minute local cap -> 2026_03_22_run_0002 scored 2.2946
- Apply one upstream-proven local tactic next: quantization-focused weight decay on the current sliding-window official-split path -> 2026_03_22_run_0003 scored 2.2947

## Latest Tested Idea
- Re-run the mixed-quantization sliding-window official-split path once to confirm the new local best under the 10-minute cap
- Result: 2.2935
- Contributor: github:101
