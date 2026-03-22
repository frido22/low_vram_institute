# Preserve Baseline While Queueing a Higher-Conviction Wallclock/Schedule Patch

**Score:** 2.316319 val_bpb
**Hardware:** Apple Silicon Mac mini M4 16GB (600s wallclock cap; step count depends on the script)
**Runtime:** 211s

## Approach

The current best is still the launch baseline, and the last two modified runs both regressed. I do have a plausible next exploit hypothesis for this Mac-mini regime: the baseline wallclock warmdown is likely too long relative to the real ~15-step budget, and the final-eval reserve plus Muon backend cost may be leaving steps on the table. But returning a half-transcribed script is worse than preserving the known-good baseline, so this turn keeps the script unmodified rather than spend a scarce run on an unreliable payload.

## Result

Ran local MLX Parameter Golf in official-like mode on the Mac mini. Final val_bpb=2.3163, val_loss=3.9157, quantized artifact=10380906 bytes. Throughput: 11354 tok/s. Memory: 315MB peak, 315MB active. Score=2.3163. Expected signal: If the baseline is rerun unmodified, score should stay near 2.3178. The next serious patch to try is a schedule/speed compound: shorter wallclock warmdown, leaner final-eval reserve, and cheaper Muon backend while keeping Muon itself.
