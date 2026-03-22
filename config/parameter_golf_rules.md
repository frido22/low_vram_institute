# Parameter Golf Agent Rules

## Goal

Minimize the Parameter Golf score on an Apple Silicon Mac mini (M4, 16 GB RAM).
Real upstream code path, official validation split, `MAX_WALLCLOCK_SECONDS=600`.
Hardware is the main intentional mismatch — you get ~15 training steps, not 20,000.

## Agency

You have FULL, UNRESTRICTED agency over the training script.
Return the complete modified `train_gpt_mlx.py` as `modified_script`, or null to run unmodified.
The original is always restored after each run — be fearless.

- A single hyperparameter tweak can be the winning move (warmdown_iters 1200→15 was a 2.5x improvement)
- But you can also rewrite entire functions, add new classes, or replace the architecture wholesale
- There is NO limit on ambition — let the hypothesis determine the scope
- Think like a researcher who only gets 15 gradient steps — what matters most with so few updates?

## Decision Priorities

1. COMPOUND: Build on the current best changes (see the diff). Don't start from scratch.
2. REASON: Think about why a technique would help with only ~15 gradient updates.
3. DIVERSIFY: Check idea categories in lessons. Don't repeat exhausted categories.
4. LEARN: Study what worked and what failed. Form hypotheses, not just random trials.
5. VALIDATE SPARINGLY: Only validate when the improvement is large (>0.01) and the run was truly novel.

## Hard Rules

- Model + code must fit in 16MB (16,000,000 bytes) compressed — this is the Parameter Golf size cap
- Never train on validation data or leak validation into training
- Never weaken the 600s wallclock cap
- Never remove or bypass final evaluation (`final_int8_zlib_roundtrip_exact`)
- Never change data/tokenizer path resolution
- Never import network libraries (socket, http, urllib, requests) or subprocess
- Keep scripts under 1500 lines (upstream rule — enforced in the script header itself)
- Scoring metric is val_bpb (bits per byte) — lower is better
- The quantized artifact size is reported as `quantized_artifact_bytes` — watch it, stay under 16MB

## Mac Mini Reality

- ~15 training steps in 10 minutes (vs ~20,000 on H100)
- 16GB unified memory — cannot run models that need >14GB
- Throughput: ~524K tokens per step, ~40 seconds per step
- Learning rate schedule, initialization, and per-step efficiency matter enormously
- Techniques that improve final loss after 20K steps may be irrelevant with 15 steps
