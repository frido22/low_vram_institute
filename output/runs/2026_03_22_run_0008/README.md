# Run The Best Local Baseline Again

**Score:** 2.323542 val_bpb
**Hardware:** Apple Silicon Mac mini M4 16GB (600s wallclock cap; step count depends on the script)
**Runtime:** 211s

## Approach

The current winner is still the unmodified baseline at 2.31631931, and the last three modified attempts all regressed. The strongest real hypothesis from the logs is that the script is iteration-limited rather than wallclock-limited, but that requires a full-script payload and the recent modification streak argues against spending another run on an incomplete or weakly transcribed change. Under the budget policy, preserving the best known path is better than burning a scarce run on a risky malformed patch.

## Result

Ran local MLX Parameter Golf in official-like mode on the Mac mini. Final val_bpb=2.3235, val_loss=3.9279, quantized artifact=10379036 bytes. Throughput: 11337 tok/s. Memory: 315MB peak, 315MB active. Score=2.3235. Expected signal: Score should remain near the current best band around 2.316-2.318; if it does, that confirms the plateau is real and that the next run should be a higher-conviction wallclock-usage patch rather than another minor schedule or optimizer tweak.
