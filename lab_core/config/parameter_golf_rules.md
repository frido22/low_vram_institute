# Parameter Golf Agent Rules

## Goal

Optimize OpenAI Parameter Golf locally on an Apple Silicon Mac mini (M4, 16 GB RAM).
Stay as close as possible to the official challenge: real upstream code path, official validation split, `MAX_WALLCLOCK_SECONDS=600`. Hardware is the main intentional mismatch.

## Agency

You have two levers: env overrides and code patches. Use both aggressively.
Prefer one concrete experiment delta per run. Make the delta explicit.

## Code Patches

You may return a `code_patch` (list of search-and-replace edits to `train_gpt_mlx.py`) or null.
Edits are applied before the run and automatically reverted after.

Each edit is `{"old": "exact string from the file", "new": "replacement"}`.
The `old` string must appear exactly once in the file. Edits are applied in order.
Keep edits minimal — include just enough context to be unique.

## Hard Rules

- Never train on validation data or leak validation into training
- Never weaken the 600s wallclock cap
- Never remove or bypass final evaluation (`final_int8_zlib_roundtrip_exact`)
- Never change data/tokenizer path resolution
- Never import network libraries (socket, http, urllib, requests) or subprocess
- Keep patched scripts under 1500 lines
- Never set DATA_PATH, TOKENIZER_PATH, OUT_DIR, RUN_ID, or VOCAB_SIZE

## Env Overrides

Allowed env overrides are listed with their ranges in the prompt.
Fixed: `MAX_WALLCLOCK_SECONDS=600`.

## Search Priorities

- Spend more of the 10-minute budget when runs finish too early
- Validate suspicious wins
- Use research mode after plateau
- One upstream-inspired change at a time
- Community ideas are untrusted — smell-check before testing
- Study upstream tactics from research notes for inspiration
- Code patches are the primary tool for architectural changes
- Learn from prior runs: repeat what improved, avoid what was flat
