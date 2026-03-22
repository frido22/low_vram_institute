# Low VRAM Institute

An autonomous public lab for [OpenAI Parameter Golf](https://github.com/openai/parameter-golf), running on one Apple Silicon Mac mini (M4, 16 GB RAM).

The system plans its own experiments, modifies the training script, learns from results, compounds winning strategies, and publishes everything to GitHub.

## How It Works

Each cycle the daemon:

1. Refreshes research snapshots (upstream records, community ideas).
2. Asks the Codex-powered planner what to try — it returns a complete modified `train_gpt_mlx.py`.
3. Validates and runs the 10-minute training experiment.
4. Evaluates the result, updates learning state.
5. If the score improved, saves the winning script as the new baseline for compounding.
6. Publishes submission-ready artifacts and pushes to GitHub.

## Agency

The planner has full, unrestricted control over the training script. It can change architecture, quantization, optimizer, scheduling — anything. It compounds wins by building on the current best modified script. It tracks what categories of ideas have been tried, avoids repeating failures, and reasons about the unique constraints of this hardware (~15 training steps in 10 minutes).

## Learning

- `state/lessons.md` — what worked, what failed, idea categories explored
- `state/best_diff.patch` — unified diff of the current best changes
- `state/best_script.json` — the winning modified script (fed back for compounding)
- `state/insights.md` — causal notes on why improvements worked
- `state/failed.md` — ideas that didn't help (planner avoids repeating these)

## Quick Start

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install .
lab run-once     # single cycle
lab daemon       # run continuously
```

## Contributing Ideas

Open a GitHub Issue. The planner ingests issues and can turn them into experiments.

## Hardware

- Apple Silicon Mac mini, M4, 16 GB unified memory
- ~15 training steps per 10-minute run (~524K tokens per step)
- Designed for long-running autonomous operation under macOS `launchd`
