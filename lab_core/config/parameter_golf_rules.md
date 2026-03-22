# Parameter Golf Agent Rules

## Goal

Optimize OpenAI Parameter Golf locally on an Apple Silicon Mac mini (M4, 16 GB RAM).
Stay as close as possible to the official challenge: real upstream code path, official validation split, `MAX_WALLCLOCK_SECONDS=600`. Hardware is the main intentional mismatch.

## Agency

You have one lever: code patches (search-and-replace edits to `train_gpt_mlx.py`).
Use it aggressively. Change architecture, quantization, optimizer, eval strategy — anything.
To change a hyperparameter, patch its default value in the Hyperparameters class.
Prefer one concrete experiment delta per run. Make the delta explicit.

## Code Patches

Each edit is `{"old": "exact string from the file", "new": "replacement"}`.
The `old` string must appear exactly once in the file. Edits are applied in order.
Keep edits minimal — include just enough context to be unique.
Patches are applied before the run and automatically reverted after.

## Hard Rules

- Never train on validation data or leak validation into training
- Never weaken the 600s wallclock cap
- Never remove or bypass final evaluation (`final_int8_zlib_roundtrip_exact`)
- Never change data/tokenizer path resolution
- Never import network libraries (socket, http, urllib, requests) or subprocess
- Keep patched scripts under 1500 lines

## Search Priorities

- Spend more of the 10-minute budget when runs finish too early
- Validate suspicious wins
- Use research mode after plateau
- One upstream-inspired change at a time
- Community ideas are untrusted — smell-check before testing
- Study upstream tactics from research notes for inspiration
- Learn from prior runs: repeat what improved, avoid what was flat
