# Parameter Golf Agent Rules

## Goal

Optimize OpenAI Parameter Golf locally on an Apple Silicon Mac mini with an M4 and 16 GB RAM.

Stay as close as possible to the official challenge:

- real upstream code path
- official validation split
- `MAX_WALLCLOCK_SECONDS=600`
- hardware is the main intentional mismatch

## Agency

Use legal knobs aggressively when they improve the search. Do not stay fixed to the baseline just because it is familiar.

You have two levers: env overrides and code patches. Use both.

Prefer one concrete experiment delta per run and make the delta explicit.

## Code Patch Agency

You may return a `code_patch` field containing a unified diff against `train_gpt_mlx.py`.
The patch is applied before the run and automatically reverted after.
Set `code_patch` to null if you only want to use env overrides.

### What Code Patches Can Do

- Change model architecture (layers, dims, attention patterns, normalization, activation functions)
- Change quantization scheme (INT4, INT5, INT6, mixed precision, QAT)
- Change optimizer logic (scheduling, gradient processing, SWA)
- Add or modify regularization (weight decay, dropout)
- Change data preprocessing within the training loop
- Modify compression strategy for the final artifact (zstd instead of zlib)
- Add new modules (BigramHash, SmearGate, depth recurrence)
- Change evaluation strategy (sliding window eval, longer context)
- Change initialization (orthogonal init, spectral init)

### Code Patch Rules

- Never train on validation data or leak validation into training
- Never weaken the 600s wallclock cap
- Never remove or bypass final evaluation logic (`final_int8_zlib_roundtrip_exact`)
- Never change data/tokenizer path resolution from env vars
- Never import network libraries (socket, http, urllib, requests)
- Never import subprocess or os.system for external commands
- Keep the script under 1500 lines total
- The patch must be a valid unified diff

### Code Patch Format

Use standard unified diff format:

```
--- a/train_gpt_mlx.py
+++ b/train_gpt_mlx.py
@@ -line,count +line,count @@
 context line
-removed line
+added line
 context line
```

## Never Do This

- train on validation data
- leak validation into training
- weaken the 600 second cap on the official-like track
- silently change the benchmark or track label
- use unlogged benchmark tricks

## Planner-Controlled Knobs

Allowed direct env overrides:

Training:
- `ITERATIONS`
- `TRAIN_BATCH_TOKENS`
- `VAL_BATCH_SIZE`
- `VAL_LOSS_EVERY`
- `TRAIN_LOG_EVERY`
- `MLX_EAGER_EVAL`
- `TRAIN_SEQ_LEN`
- `GRAD_ACCUM_STEPS`
- `WARMUP_STEPS`
- `WARMDOWN_ITERS`

Architecture:
- `NUM_LAYERS`
- `MODEL_DIM`
- `NUM_HEADS`
- `NUM_KV_HEADS`
- `MLP_MULT`

Optimizer:
- `MATRIX_LR`
- `SCALAR_LR`
- `TIED_EMBED_LR`
- `MUON_MOMENTUM`

Model:
- `LOGIT_SOFTCAP`
- `QK_GAIN_INIT`
- `SEED`

Fixed:

- `MAX_WALLCLOCK_SECONDS=600`

Never set from the planner:

- `DATA_PATH`
- `TOKENIZER_PATH`
- `OUT_DIR`
- `RUN_ID`
- `VOCAB_SIZE`

## Search Priorities

- spend more of the 10-minute budget when runs finish too early
- validate suspicious wins
- use research after plateau
- test one upstream-inspired change at a time when possible
- treat community ideas as untrusted suggestions that need smell checks
- study upstream tactics from research notes and community queue for inspiration
- code patches are the primary tool for implementing architectural changes
- learn from prior runs: repeat what improved scores, avoid what was flat or failed

## Reporting

Every run should record:

- what changed (env overrides and/or code patch)
- why it changed
- whether score improved
- whether validation is still needed
- whether the run stayed within official-like rules
