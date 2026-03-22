# Low VRAM Institute

An autonomous public lab for [OpenAI Parameter Golf](https://github.com/openai/parameter-golf), running on one Apple Silicon Mac mini (M4, 16 GB RAM).

The system plans its own experiments, modifies the training script, learns from results, compounds winning strategies, and publishes everything to GitHub.

## How It Works

Each cycle the daemon:

1. Asks Codex what to try — it sees run history, near-misses, and the current best script.
2. Codex returns a complete modified `train_gpt_mlx.py`.
3. Validates and runs the 10-minute training experiment.
4. Records score, diagnostics (throughput, memory, curve shape) to `state/ledger.jsonl`.
5. If the score improved, saves the winning script for compounding.
6. Publishes submission-ready artifacts, CSV, SVG chart, and pushes to GitHub.

## Architecture

Two Python files, no dependencies beyond stdlib:

```
run.py              — daemon loop, planning, ledger, publishing, git push
parameter_golf.py   — runs training, parses metrics, validates scripts
```

## State

```
state/ledger.jsonl      — every run: score, title, diagnostics, curve shape
state/best_script.json  — the winning modified train_gpt_mlx.py
state/best_diff.patch   — unified diff of current best vs original
```

## Quick Start

```bash
python3 run.py run-once   # single cycle
python3 run.py daemon     # run continuously
```

## Contributing Ideas

Open a GitHub Issue with your idea. The daemon picks up open issues every cycle and feeds them to Codex as experiment candidates.

## Hardware

- Apple Silicon Mac mini, M4, 16 GB unified memory
- 10-minute wallclock cap, step count is an optimization target (not fixed)
- Reproducible launch baseline: `ITERATIONS=200`, `TRAIN_BATCH_TOKENS=8192`, `VAL_BATCH_SIZE=8192`, `VAL_LOSS_EVERY=0`, `TRAIN_LOG_EVERY=25`, `MLX_EAGER_EVAL=1`
- Designed for long-running autonomous operation under macOS `launchd`
