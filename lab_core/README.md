# lab_core

`lab_core` is the private control plane for an always-on public autonomous lab running on an Apple Silicon Mac mini. It is now focused on a single objective: local optimization for the OpenAI Parameter Golf challenge on an M4 Mac mini with 16 GB RAM. It owns planning, execution, evaluation, recovery, GitHub intake, research snapshots, and publication into `lab_public`.

## Principles

- Always on through a local supervisor, checkpoints, lock files, retries, and resume state.
- High agency through a planner that chooses between `explore`, `exploit`, `validate`, `research`, and `community` in service of local Parameter Golf progress.
- Public by default through a publisher that emits one run package per cycle plus updated public status pages.
- Deterministic state through small append-only files in `state/`, `logs/`, and `snapshots/`.
- One-model backend in v1: Codex authenticated locally via ChatGPT. The service wrapper is intentionally local and replaceable, but no alternative providers are wired in.

## Public Contract

This project is designed to publish aggressively.

The machine runs locally, but the results are pushed here:

- public run packages in `../lab_public/runs/`
- public status pages in `../lab_public/public/`
- contributor credit when outside ideas are tested

Community members should submit ideas through GitHub Issues. Those issues are normalized into the intake queue and can be selected by the planner for public experiments.

## Local Parameter Golf Target

The active target machine is:

- Apple Silicon Mac mini
- M4
- 16 GB unified memory

The adapter now targets the upstream `train_gpt_mlx.py` workflow from a local checkout of `openai/parameter-golf` under `../third_party/parameter-golf`.

## Layout

```text
lab_core/
  src/lab_core/
    adapters/
    services/
    cli.py
    config.py
    evaluator.py
    executor.py
    planner.py
    publisher.py
    supervisor.py
  state/
  logs/
  snapshots/research/
  launchd/
  ARCHITECTURE.md
  MANIFESTO.md
  ROADMAP_V2.md
```

## Run

Create a virtual environment, install the package, then run one cycle:

```bash
cd lab_core
python3 -m venv .venv
source .venv/bin/activate
python -m ensurepip --upgrade
pip install .
lab-core run-once
```

Run the long-lived local daemon loop:

```bash
lab-core daemon
```

Source-only mode without installation:

```bash
PYTHONPATH=src python3 -m lab_core.cli run-once
```

The daemon writes:

- machine state in `state/`
- run and heartbeat logs in `logs/`
- research snapshots in `snapshots/research/`
- public artifacts into `../lab_public/`

## Parameter Golf Bootstrap

Set up the local MLX workspace and download the smallest practical dataset slice with:

```bash
bash /Users/frido_mac/Projects/low_vram_institute/lab_core/scripts/bootstrap_parameter_golf.sh
```

## State Files

- `state/current_state.json`
- `state/insights.md`
- `state/ideas_queue.md`
- `state/rejected_ideas.md`
- `state/best_runs.json`
- `state/agenda.md`
- `state/community_queue.jsonl`

## GitHub Token Setup

Set a fine-grained GitHub token in the shell or `launchd` environment:

```bash
export GITHUB_TOKEN=...
```

For unattended runs on macOS, prefer a local untracked env file:

```bash
mkdir -p /Users/frido_mac/.config/low-vram-lab
cat > /Users/frido_mac/.config/low-vram-lab/env.sh
```

Then place:

```bash
export GITHUB_TOKEN='YOUR_FINE_GRAINED_PAT'
```

Finish with `Ctrl-D`, then lock down permissions:

```bash
chmod 600 /Users/frido_mac/.config/low-vram-lab/env.sh
```

The runtime config in `config/runtime.json` keeps the allowed remote pinned to one repository. The publisher refuses to push anywhere else.

When `GITHUB_TOKEN` is present, the publisher uses it only for the git subprocess and avoids relying on GUI Keychain access.

## What Is Implemented In v1

- Supervisor with lock file, heartbeat, stage checkpoints, stale lock cleanup, backoff, and health checks
- Planner with five research modes and live Codex-backed plan generation
- Executor and evaluator wired to a local MLX Parameter Golf adapter
- Publisher that writes run packages, ledger rows, public status pages, `run.log`, `metrics.jsonl`, and `analysis.md` when available
- GitHub intake reader for issue snapshots and live issue ingestion for the configured repo
- Local research snapshot pipeline for deterministic source fetches from config
- Launchd plist template for boot-time startup on macOS

## What Is Still Stubbed

- Plot generation is not implemented yet
- The current local track is a Mac mini proxy, not an official 8xH100 submission path
