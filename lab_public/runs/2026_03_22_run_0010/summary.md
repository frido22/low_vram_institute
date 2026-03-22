# 2026_03_22_run_0010

## What was tried
Test the queued official-best recipe as one bounded local reproduction: int5-funded 10th layer plus BigramHash(10240) on the official-split mixed-quant path under the 10-minute cap

## Why it was tried
Plateau count is 3, and the last three non-validate runs all regressed versus the validated best (2.29350473): bigram add-on alone scored 2.2940162, SWA(0.4) alone scored 2.29561606, and the latest research probe scored 2.29472786. That pattern argues against more isolated tweaks. The strongest concrete next test is the queued public recipe that matches repeated upstream tactics and the current upstream leaderboard summary: mixed quantization, bigram features, weight decay, and SWA, with the missing local mismatch being the int5-funded extra depth. The idea passes basic smell checks because it is specific, artifact-budget-aware, upstream-consistent, and directly testable on the real local code path without changing the evaluation protocol.

## Main result
- Score: 2.2923
- Runtime: 180.62s
- Passed: True
- Needs validation: True

## What changed
`parameter_golf` adapter run for mode `community`.

## Belief update
Ran local MLX Parameter Golf in official-like mode on the Mac mini. Final val_bpb=2.2923, val_loss=3.8717, quantized artifact=10261989 bytes. Score=2.2923. Expected signal: Positive signal is a pass within the 10-minute wallclock and a score at or below the current best 2.29350473, especially if the 10-layer int5-funded path recovers the regressions seen from bigram-only and SWA-only probes. Negative signal is another regression or budget/time failure, which would falsify the combined public recipe on M4 hardware and justify switching back to research.

## What next
Positive signal is a pass within the 10-minute wallclock and a score at or below the current best 2.29350473, especially if the 10-layer int5-funded path recovers the regressions seen from bigram-only and SWA-only probes. Negative signal is another regression or budget/time failure, which would falsify the combined public recipe on M4 hardware and justify switching back to research.
