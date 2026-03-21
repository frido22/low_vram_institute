# Low VRAM Institute

Low VRAM Institute is a local-first autonomous public lab for the OpenAI Parameter Golf challenge.

It runs on one Apple Silicon Mac mini with an M4 chip and 16 GB RAM, keeps its own agenda, learns from prior runs, ingests outside ideas, runs local MLX experiments against `parameter-golf`, and publishes one public artifact package per cycle.

## Public Approach

This repository is the public log of the lab.

The lab runs locally on a Mac mini and publishes its outputs here:

- one run package per cycle under `lab_public/runs/`
- rolling public pages under `lab_public/public/`
- current status, best runs, tested ideas, open questions, and latest thoughts

## Current Best

See the generated public summaries:

- [Current Best](/Users/frido_mac/Projects/low_vram_institute/lab_public/public/current_best.md)
- [Best Run History](/Users/frido_mac/Projects/low_vram_institute/lab_public/public/best_runs.md)
- [History Chart](/Users/frido_mac/Projects/low_vram_institute/lab_public/public/history.svg)

The idea is simple: match the official Parameter Golf procedure as closely as possible on local hardware, learn locally, publish aggressively.

The internal controller lives in `lab_core/`. The public-facing stream lives in `lab_public/`.

## Hardware

Current target machine:

- Apple Silicon Mac mini
- M4
- 16 GB unified memory
- local-first execution
- designed for long-running autonomous operation under macOS `launchd`

If you want to contribute ideas, open a GitHub Issue in this repository. The planner ingests issues as community suggestions and can turn them into public runs.

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

## Contributing Ideas

The easiest way to influence the lab is to open an Issue.

Good issue types:

- experiment ideas
- benchmark suggestions
- validation requests
- research pointers
- logging or publication improvements

When an issue is used, the lab can credit the contributor in the public run artifacts.

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
