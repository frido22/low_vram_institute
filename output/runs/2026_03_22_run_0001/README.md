# Mac-Mini Launch Baseline

**Score:** 2.317817 val_bpb
**Hardware:** Apple Silicon Mac mini M4 16GB (600s wallclock cap; step count depends on the script)
**Runtime:** 211s

## Approach

There is no local data yet. The highest-value first run is the unmodified MLX script under the lab’s injected Mac-mini launch baseline env, so we measure true local step count, eval reserve behavior, throughput, memory, and final artifact size before spending scarce runs on architecture or optimizer changes. The workspace already forces the official local runtime knobs (`ITERATIONS=200`, `TRAIN_BATCH_TOKENS=8192`, `VAL_BATCH_SIZE=8192`, `VAL_LOSS_EVERY=0`, `TRAIN_LOG_EVERY=25`, `MAX_WALLCLOCK_SECONDS=600`, `MLX_EAGER_EVAL=1`, `MLX_MAX_MICROBATCH_TOKENS=8192`), so a code diff is not yet necessary to get the correct baseline.

## Result

Ran local MLX Parameter Golf in official-like mode on the Mac mini. Final val_bpb=2.3178, val_loss=3.9182, quantized artifact=10372923 bytes. Throughput: 11351 tok/s. Memory: 316MB peak, 316MB active. Score=2.3178. Expected signal: A clean baseline read on completed steps, `step_avg`, `avg_tok_s`, peak memory, final eval reserve adequacy, and `final_int8_zlib_roundtrip_exact val_bpb`. That data will determine whether the next move should be speed work, batch-shape changes, or a smaller/faster architecture.
