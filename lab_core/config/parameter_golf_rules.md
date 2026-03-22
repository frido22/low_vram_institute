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

Prefer one concrete experiment delta per run and make the delta explicit.

## Never Do This

- train on validation data
- leak validation into training
- weaken the 600 second cap on the official-like track
- silently change the benchmark or track label
- use unlogged benchmark tricks

## Planner-Controlled Knobs

Allowed direct env overrides:

- `ITERATIONS`
- `TRAIN_BATCH_TOKENS`
- `VAL_BATCH_SIZE`
- `VAL_LOSS_EVERY`
- `TRAIN_LOG_EVERY`
- `MLX_EAGER_EVAL`

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

## Reporting

Every run should record:

- what changed
- why it changed
- whether score improved
- whether validation is still needed
- whether the run stayed within official-like rules
