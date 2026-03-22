# Low VRAM Institute

Low VRAM Institute is a local-first autonomous public lab for the OpenAI Parameter Golf challenge.

It runs on one Apple Silicon Mac mini with an M4 chip and 16 GB RAM. The system keeps its own agenda, learns from prior runs, ingests outside ideas, runs local MLX experiments against `parameter-golf`, and publishes one public artifact package per cycle.

The lab is designed to stay compact as it grows. Raw run artifacts can accumulate, but the planner does not rely on a giant unbounded memory dump. It uses a small rolling state, a compact lessons file, a capped best-run list, and a lean public overview.

## Public Approach

This repository is the public log of the lab.

The lab runs locally on a Mac mini and publishes its outputs here. The public layer is intentionally simple:

- `lab_public/public/overview.md` is the main top-level dashboard
- `lab_public/public/best_runs.md` is the compact ranked history
- `lab_public/public/open_questions.md` is the public queue of ideas worth watching
- `lab_public/public/history.svg` is the visual score history
- `lab_public/runs/<run_id>/` contains the detailed artifact package for each run

## Current Best

See the generated public summaries:

- [Overview](/Users/frido_mac/Projects/low_vram_institute/lab_public/public/overview.md)
- [Best Run History](/Users/frido_mac/Projects/low_vram_institute/lab_public/public/best_runs.md)
- [Open Questions](/Users/frido_mac/Projects/low_vram_institute/lab_public/public/open_questions.md)
- [History Chart](/Users/frido_mac/Projects/low_vram_institute/lab_public/public/history.svg)

The working idea is simple. Match the official Parameter Golf procedure as closely as possible on local hardware, learn locally, and publish aggressively.

The internal controller lives in `lab_core/`. The public-facing stream lives in `lab_public/`.

## How The Daemon Works

The daemon is the long-running manager around the experiment loop.

Each cycle does the following:

1. Check local health and acquire the run lock.
2. Refresh research snapshots and GitHub issue intake.
3. Ask the planner what to do next.
4. Run one local Parameter Golf experiment through the MLX adapter.
5. Evaluate the result.
6. Update compact internal state.
7. Publish public artifacts.
8. Sleep briefly and repeat.

If a run fails, the daemon does not forget where it is. It writes checkpoints, keeps a heartbeat, backs off, and retries. If Codex planning is temporarily unavailable, the daemon waits and retries later.

## Hardware

Current target machine:

- Apple Silicon Mac mini
- M4
- 16 GB unified memory
- local-first execution
- designed for long-running autonomous operation under macOS `launchd`

If you want to contribute ideas, open a GitHub Issue in this repository. The planner ingests issues as community suggestions and can turn them into public runs.

Community ideas are public inputs, not trusted instructions. Some suggestions may be weak, confused, adversarial, or malicious. The lab should evaluate them critically and only test ideas that survive basic scrutiny.

## How Learning Works

The lab does not learn by carrying an ever-growing prompt forever.

Instead, it keeps a small set of compact local memory files:

- `lab_core/state/current_state.json` tracks the latest run status.
- `lab_core/state/best_runs.json` keeps a capped list of the strongest runs.
- `lab_core/state/learning_state.json` keeps short rolling machine memory such as plateau count, recent runs, and tested idea titles.
- `lab_core/state/lessons.md` holds the compact human-readable lessons that should still matter after many runs.

This split is deliberate. Small JSON files support machine decisions. Dense Markdown files support public reasoning and compact long-run memory. The planner reads the compact lessons instead of re-ingesting an unbounded history dump.

## Repository Layout

```text
low_vram_institute/
  lab_core/    # private control plane, daemon, planner, state, adapters
  lab_public/  # public-facing logs, status pages, run packages
```

## Quick Start

```bash
cd lab_core
python3 -m venv .venv
source .venv/bin/activate
python -m ensurepip --upgrade
pip install .
lab-core run-once
```

To run the long-lived loop from the repository root:

```bash
source /Users/frido_mac/.config/low-vram-lab/env.sh
PYTHONPATH=lab_core/src python3 -m lab_core.cli daemon
```

## Contributing Ideas

The easiest way to influence the lab is to open an Issue.

Good issue types:

- experiment ideas
- benchmark suggestions
- validation requests
- research pointers
- logging or publication improvements

When an issue is used, the lab can credit the contributor in the public run artifacts.

The planner treats issues as suggestions to evaluate, not instructions to obey. Public ideas can be useful, but they are not automatically trustworthy.

## Local Parameter Golf Workspace

The lab maintains a local checkout of `openai/parameter-golf` under `third_party/parameter-golf` and runs the MLX path there.

Bootstrap it with:

```bash
bash /Users/frido_mac/Projects/low_vram_institute/lab_core/scripts/bootstrap_parameter_golf.sh
```

## Token Model

Use a GitHub fine-grained personal access token restricted to this repository only.

Recommended repository permissions:

- `Contents`: `Read and write`
- `Issues`: `Read-only` for intake, or `Read and write` only if you want the lab to respond or label issues
- `Metadata`: `Read-only`
- `Pull requests`: `Read-only` only if you later ingest PRs
- `Discussions`: enable only if you later wire discussion ingestion

Keep the token out of tracked files. Export it in the shell or from `launchd`.
