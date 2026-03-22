# Tested Ideas

- Test the queued official-best recipe as one bounded local reproduction: int5-funded 10th layer plus BigramHash(10240) on the official-split mixed-quant path under the 10-minute cap -> 2026_03_22_run_0010 scored 2.2923
- Re-run the mixed-quantization sliding-window official-split path once to confirm the new local best under the 10-minute cap -> 2026_03_22_run_0006 scored 2.2935
- Test mixed quantization on the official-split sliding-window path under the 10-minute local cap -> 2026_03_22_run_0005 scored 2.2939
- Add bigram features to the validated mixed-quantization sliding-window official-split path -> 2026_03_22_run_0007 scored 2.2940
- Apply one upstream-proven local tactic next: sliding-window evaluation on the official validation split -> 2026_03_22_run_0001 scored 2.2944
- Establish an upstream-local baseline on M4 under the 10-minute cap -> 2026_03_21_run_0001 scored 2.2944
- Research the next upstream tactic to test on the official-split local path: mixed quantization before more exploit runs -> 2026_03_22_run_0004 scored 2.2945
- Re-run sliding-window evaluation once on the official validation split under the 10-minute local cap -> 2026_03_22_run_0002 scored 2.2946
- Isolate one genuinely new upstream tactic after two local regressions: verify whether int5-funded depth or BigramHash(10240) is the next official-like test -> 2026_03_22_run_0009 scored 2.2947
- Apply one upstream-proven local tactic next: quantization-focused weight decay on the current sliding-window official-split path -> 2026_03_22_run_0003 scored 2.2947

## Latest Tested Idea
- Test the queued official-best recipe as one bounded local reproduction: int5-funded 10th layer plus BigramHash(10240) on the official-split mixed-quant path under the 10-minute cap
- Result: 2.2923
- Contributor: github:4114281267
