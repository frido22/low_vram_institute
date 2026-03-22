# Tested Ideas

- Apply one upstream-proven local tactic next: sliding-window evaluation on the official validation split -> 2026_03_22_run_0001 scored 2.2944
- Establish an upstream-local baseline on M4 under the 10-minute cap -> 2026_03_21_run_0001 scored 2.2944
- Re-run sliding-window evaluation once on the official validation split under the 10-minute local cap -> 2026_03_22_run_0002 scored 2.2946
- Apply one upstream-proven local tactic next: quantization-focused weight decay on the current sliding-window official-split path -> 2026_03_22_run_0003 scored 2.2947

## Latest Tested Idea
- Apply one upstream-proven local tactic next: quantization-focused weight decay on the current sliding-window official-split path
- Result: 2.2947
- Contributor: weight decay for quantization
