# Low VRAM Institute

An autonomous public lab for [OpenAI Parameter Golf](https://github.com/openai/parameter-golf), running on one Apple Silicon Mac mini (M4, 16 GB RAM).

The system plans its own experiments, modifies the training script, learns from results, compounds winning strategies, and publishes results plus state to GitHub.

## How It Works

Each cycle the daemon:

1. Uses a saved next plan if one is ready; otherwise asks Codex what to try.
2. Codex returns a complete modified `train_gpt_mlx.py`.
3. Starts preparing the next plan in the background while the current run trains.
4. Validates and runs the 10-minute training experiment.
5. Records the result to `state/ledger.jsonl`.
6. If `final_int8_zlib_roundtrip_exact val_bpb` improved on the valid main track, saves the winning script for compounding.
7. Publishes per-run artifacts, state, and pushes to GitHub.

## Architecture

Two Python files, no dependencies beyond stdlib:

```
run.py              — daemon loop, planning, ledger, publishing, git push
parameter_golf.py   — runs training, parses final exact metric, validates scripts
```

## State

```
state/ledger.jsonl      — append-only run history
state/best_script.py    — the current best valid train_gpt_mlx.py
state/next_plan.md      — next planned experiment when ready
state/pending_plan.md   — current run plan, used for restart safety
```

## Quick Start

```bash
python3 run.py run-once   # single cycle
python3 run.py daemon     # run continuously
```

## Hardware

- Apple Silicon Mac mini, M4, 16 GB unified memory
- 10-minute wallclock cap, step count is an optimization target (not fixed)
- Reproducible launch baseline: `ITERATIONS=200`, `TRAIN_BATCH_TOKENS=8192`, `VAL_BATCH_SIZE=8192`, `VAL_LOSS_EVERY=0`, `TRAIN_LOG_EVERY=25`, `MLX_EAGER_EVAL=1`
- Designed to run continuously in a long-lived shell such as `screen`
