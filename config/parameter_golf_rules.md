# Parameter Golf Agent Rules

## Goal

Minimize the Parameter Golf score on an Apple Silicon Mac mini (M4, 16 GB RAM).
Real upstream code path, official validation split, `MAX_WALLCLOCK_SECONDS=600`.

## Agency

You have FULL, UNRESTRICTED agency over the training script.
Return the complete modified `train_gpt_mlx.py` as `modified_script`, or null to run unmodified.
The original is always restored after each run — be fearless.

- A single hyperparameter tweak can be the winning move (warmdown_iters 1200→15 was a 2.5x improvement)
- But you can also rewrite entire functions, add new classes, or replace the architecture wholesale
- There is NO limit on ambition — let the hypothesis determine the scope
- You can also optimize the code itself to run faster — more training steps in 600s = better results

## Decision Priorities

1. COMPOUND: Build on the current best changes (see the diff). Don't start from scratch.
2. REASON: Think about why a technique would help given the limited step budget on this hardware.
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

- The baseline gets ~15 training steps in 10 minutes — but this is NOT a fixed limit
- Optimizing code speed (faster forward/backward, less overhead) means more steps in the same 600s
- More steps = more gradient updates = potentially better final score
- 16GB unified memory — cannot run models that need >14GB
- Throughput and step count are reported per run — use them to track optimization impact
- Learning rate schedule, initialization, and per-step efficiency all matter
- Techniques that need thousands of steps to pay off may not transfer — reason about step budget
