# Low VRAM Institute

An autonomous public lab for the [OpenAI Parameter Golf](https://github.com/openai/parameter-golf) challenge, running on one Apple Silicon Mac mini (M4, 16 GB RAM).

The system keeps its own agenda, learns from prior runs, ingests outside ideas, and publishes one public artifact package per cycle. It can modify the training script itself — generating code patches to try different architectures, quantization schemes, and training strategies.

## How It Works

Each cycle:

1. Acquire run lock and check health.
2. Refresh research snapshots and community ideas from GitHub issues.
3. Ask the Codex-powered planner what to try next (mode, env overrides, code patch).
4. Apply the code patch to `train_gpt_mlx.py` if one was generated.
5. Run the MLX training experiment under the 10-minute cap.
6. Restore the original script, evaluate results, update learning state.
7. Publish public artifacts and push to GitHub.
8. Sleep and repeat.

If a run fails (bad patch, OOM, Codex unavailable), the daemon restores the original script, backs off, and retries.

## Code Patches

The planner's only lever is code patches — search-and-replace edits to `train_gpt_mlx.py`. It can change anything: architecture, quantization, optimizer, eval strategy, hyperparameters. Patches are applied before each run and always reverted after. If a patch fails to apply, the system retries up to 5 times with error feedback before falling back to running the unmodified script.

## Safety Rails

- `MAX_WALLCLOCK_SECONDS=600` is fixed and cannot be overridden.
- Patched scripts must compile, stay under 1500 lines, and cannot import network libraries.
- The final evaluation marker (`final_int8_zlib_roundtrip_exact`) must remain intact.
- The original `train_gpt_mlx.py` is always restored after each run.
- Crash recovery: backup files are restored on startup if a previous run was interrupted.

## Learning

The lab learns across runs through compact, bounded state files:

- `state/current_state.json` — latest run status
- `state/best_runs.json` — capped ranked history (top 10)
- `state/learning_state.json` — rolling memory: plateau count, recent runs (last 8), tested ideas
- `state/lessons.md` — compact human-readable patterns: experiment deltas, repeated signals, tested ideas

The planner reads these each cycle to decide what to try next. State files stay small by design — no unbounded history dumps.

## Public Layer

- `lab_public/public/overview.md` — main dashboard
- `lab_public/public/best_runs.md` — ranked run history
- `lab_public/public/open_questions.md` — community idea queue
- `lab_public/public/history.svg` — visual score chart
- `lab_public/runs/<run_id>/` — per-run artifact package (summary, metrics, logs, analysis)

## Repository Layout

```text
low_vram_institute/
  lab_core/        # control plane: daemon, planner, adapters, state
  lab_public/      # public artifact stream: run packages, dashboards
  third_party/     # local parameter-golf checkout
```

## Quick Start

```bash
cd lab_core
python3 -m venv .venv
source .venv/bin/activate
pip install .
lab-core run-once
```

Long-running daemon:

```bash
PYTHONPATH=lab_core/src python3 -m lab_core.cli daemon
```

## Contributing Ideas

Open a GitHub Issue. The planner ingests issues as community suggestions and can turn them into runs, crediting the contributor in the public artifacts.

Community ideas are evaluated critically — not all suggestions will be tested.

## Hardware

- Apple Silicon Mac mini, M4, 16 GB unified memory
- Designed for long-running autonomous operation under macOS `launchd`
- Local-first: no cloud compute required
