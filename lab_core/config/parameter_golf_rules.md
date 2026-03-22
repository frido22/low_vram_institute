# Parameter Golf Agent Rules

## Mission

Optimize OpenAI Parameter Golf locally on an Apple Silicon Mac mini with an M4 and 16 GB RAM.

Keep the local procedure as close as possible to the official challenge:

- use the real upstream code path
- use the official validation split
- keep the wallclock cap at 600 seconds
- treat hardware as the main intentional mismatch

## Agency

Agency is preferred. If a legal knob can improve the search, use it.

Do not stay artificially fixed to the baseline when a legal mutation is available.

Prefer one concrete experiment delta per run. Make the delta explicit.

## Hard Prohibitions

- never train on validation data
- never leak validation data into training
- never change the run into a different benchmark while still labeling it as official-like
- never disable or weaken the 600 second cap on the official-like local track
- never hide a track change
- never use unlogged benchmark tricks

## Allowed Mutation Space

Use only these env knobs directly unless the repo is later extended with more:

- `ITERATIONS`
- `TRAIN_BATCH_TOKENS`
- `VAL_BATCH_SIZE`
- `VAL_LOSS_EVERY`
- `TRAIN_LOG_EVERY`
- `MLX_EAGER_EVAL`

Keep these fixed:

- `MAX_WALLCLOCK_SECONDS=600`

Do not set these from the planner:

- `DATA_PATH`
- `TOKENIZER_PATH`
- `OUT_DIR`
- `RUN_ID`
- `VOCAB_SIZE`

## Search Priorities

Prefer moves that are legal, measurable, and challenge-relevant:

- use more of the 10-minute budget when current runs finish too early
- test one concrete upstream-inspired tactic at a time when possible
- validate suspicious wins
- switch to research after plateau
- use community ideas only when they survive basic smell checks

## Public Reporting

Every run should say:

- what changed
- why it changed
- whether the score improved
- whether the result needs validation
- whether the run stayed within the official-like rules
