# Tested Ideas

- Test the queued official-best recipe as one bounded local reproduction: int5-funded 10th layer plus BigramHash(10240) on the official-split mixed-quant path under the 10-minute cap -> 2026_03_22_run_0010 scored 2.2923
- Re-run the mixed-quantization sliding-window official-split path once to confirm the new local best under the 10-minute cap -> 2026_03_22_run_0006 scored 2.2935
- Test mixed quantization on the official-split sliding-window path under the 10-minute local cap -> 2026_03_22_run_0005 scored 2.2939
- Re-run the new local best once on the official-like M4 path to confirm the int5-funded 10th-layer plus BigramHash(10240) gain under the 10-minute cap -> 2026_03_22_run_0011 scored 2.2939
- Add bigram features to the validated mixed-quantization sliding-window official-split path -> 2026_03_22_run_0007 scored 2.2940
- Isolate the next untested upstream tactic on top of the validated 10L int5-MLP + BigramHash(10240) local winner before more exploit runs -> 2026_03_22_run_0013 scored 2.2941
- Apply one upstream-proven local tactic next: sliding-window evaluation on the official validation split -> 2026_03_22_run_0001 scored 2.2944
- Establish an upstream-local baseline on M4 under the 10-minute cap -> 2026_03_21_run_0001 scored 2.2944
- Research the next upstream tactic to test on the official-split local path: mixed quantization before more exploit runs -> 2026_03_22_run_0004 scored 2.2945
- Isolate SWA start_frac=0.4 alone on the validated 10L int5-MLP + BigramHash(10240) official-split path under the 10-minute M4 cap -> 2026_03_22_run_0014 scored 2.2945

## Latest Tested Idea
- Test WD=0.04 alone on the validated 10L int5-MLP + BigramHash(10240) official-split local winner under the 10-minute M4 cap
- Result: 2.2953
- Contributor: live_repo_issues
