# Run the Best Local Baseline Again

**Score:** 2.317080 val_bpb
**Hardware:** Apple Silicon Mac mini M4 16GB (600s wallclock cap; step count depends on the script)
**Runtime:** 211s

## Approach

The strongest local evidence still favors the unmodified baseline path: run 0004 is best, while the recent schedule and optimizer edits all regressed. Because the provided state does not include a better diff to compound and validate is explicitly discouraged unless a win is clearly suspicious, the highest-confidence exploit move is to keep the winning script unchanged rather than spend another scarce run on a weak mutation.

## Result

Ran local MLX Parameter Golf in official-like mode on the Mac mini. Final val_bpb=2.3171, val_loss=3.9170, quantized artifact=10378803 bytes. Throughput: 11348 tok/s. Memory: 315MB peak, 315MB active. Score=2.3171. Expected signal: Best case: confirms the current best region and avoids burning a run on another low-conviction schedule or optimizer tweak. Failure mode: no improvement, but the run still sharpens the variance estimate around the current best baseline.
