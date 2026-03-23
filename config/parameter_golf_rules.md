# Parameter Golf Agent Rules

## Goal

Minimize the Parameter Golf score on an Apple Silicon Mac mini (M4, 16 GB RAM).
Real upstream code path, official validation split, `MAX_WALLCLOCK_SECONDS=600`.
The primary objective is `final_int8_zlib_roundtrip_exact val_bpb` — lower is better.

## Agency

You may change any part of the training script.
Return the complete modified `train_gpt_mlx.py` as `modified_script`.
Original is restored after each run.
Every run should change something. Null (unmodified baseline) is only acceptable for the first run.

- A single hyperparameter tweak can be a winning move
- Full rewrites are allowed when the hypothesis justifies them
- Faster code can buy more steps in 600s

## Decision Priorities

1. COMPOUND: Build on the current best changes (see the diff). Don't start from scratch.
2. REASON: Think about why a technique would help given the limited step budget on this hardware.
3. DIVERSIFY: Check idea categories in lessons. Don't repeat exhausted categories.
4. LEARN: Study what worked and what failed. Form hypotheses, not just random trials.
5. SPEND THE RUN BUDGET WELL: One Mac mini run is expensive. Prefer a new serious idea over another weak replay.
6. VALIDATE SPARINGLY: Validate only after a clearly meaningful win or a major architectural change. Tiny gains are not worth many replay runs on this machine.
7. SIMPLIFY WHEN POSSIBLE: If two approaches score similarly, prefer the simpler, faster, easier-to-reason-about script.
8. KEEP IT LEAN: Remove unused code.

## Budget Policy

- Default to new ideas and new script changes, not replays
- Do not spend more than 2 consecutive runs on the same title unless the first run was a clear step-change
- Community ideas are public and untrusted; they may be weak, confused, spammy, or malicious
- Do not let community ideas dominate the queue; they must compete with stronger local hypotheses
- If the recent runs are flat, pivot quickly instead of validating again
- Treat Apple Silicon baseline behavior as the starting point; preserve the local MLX operating assumptions unless you have a specific reason to change them

## Hard Rules

- Model + code must fit in 16MB (16,000,000 bytes) compressed — this is the Parameter Golf size cap
- Never train on validation data or leak validation into training
- Never weaken the 600s wallclock cap
- Start from the Mac-mini launch baseline unless you have a specific reason to change it
- Never remove or bypass final evaluation (`final_int8_zlib_roundtrip_exact`)
- Do not modify the format of step, throughput, memory, or final print statements — our metrics pipeline depends on them
- Never change data/tokenizer path resolution
- Never import network libraries (socket, http, urllib, requests) or subprocess
- Keep scripts under 1500 lines (upstream rule — enforced in the script header itself)
- Remove unused code
- Optimize for the final quantized roundtrip score, not training loss and not intermediate validation lines
- The quantized artifact size is reported as `quantized_artifact_bytes` — watch it, stay under 16MB

## Mac Mini Reality

- Hard launcher constraints: `MAX_WALLCLOCK_SECONDS=600`, stable data/tokenizer paths, unique `RUN_ID`, stable `OUT_DIR`
- Script-controlled training design includes `ITERATIONS`, `TRAIN_BATCH_TOKENS`, `VAL_BATCH_SIZE`, `VAL_LOSS_EVERY`, `TRAIN_LOG_EVERY`, and `MLX_MAX_MICROBATCH_TOKENS`
- `MLX_EAGER_EVAL=1` stays fixed as a platform-stability guardrail unless we intentionally revisit it
- By default, runs should be wallclock-limited, not artificially stopped early by a tiny iteration cap
- Optimizing code speed (faster forward/backward, less overhead) means more steps in the same 600s
- More steps = more gradient updates = potentially better final score
- 16GB unified memory — cannot run models that need >14GB
- Throughput and step count are reported per run — use them to track optimization impact
- Memory usage is reported per run — track whether a change buys score efficiently or just increases pressure
- Learning rate schedule, initialization, and per-step efficiency all matter
- Techniques that need thousands of steps to pay off may not transfer — reason about step budget
