# 2026_03_22_run_0009

## What was tried
Isolate one genuinely new upstream tactic after two local regressions: verify whether int5-funded depth or BigramHash(10240) is the next official-like test

## Why it was tried
The last validated best is run_0006 at 2.29350473, and the two follow-up exploit runs both regressed: bigram features to 2.2940162 and SWA start_frac=0.4 to 2.29561606. With plateau_count at 2, the clean next move is research rather than another exploit. The strongest queued signal is the public report of the current official best, but it is untrusted and mostly overlaps tactics already tested locally (mixed quantization, bigrams, SWA, WD). Research should therefore decompose that report against upstream records and recent local results to find the one missing tactic that is both upstream-grounded and plausibly runnable on the M4 under the 10-minute cap, instead of blindly testing the whole bundle.

## Main result
- Score: 2.2947
- Runtime: 180.65s
- Passed: True
- Needs validation: True

## What changed
`parameter_golf` adapter run for mode `research`.

## Belief update
Ran local MLX Parameter Golf in official-like mode on the Mac mini. Final val_bpb=2.2947, val_loss=3.8758, quantized artifact=10260567 bytes. Score=2.2947. Expected signal: A single concrete next exploit candidate with a short justification, ideally showing that either int5-funded extra depth or a specific bigram-hash capacity change is the highest-value new test while keeping the real upstream code path and official validation split intact.

## What next
A single concrete next exploit candidate with a short justification, ideally showing that either int5-funded extra depth or a specific bigram-hash capacity change is the highest-value new test while keeping the real upstream code path and official validation split intact.
