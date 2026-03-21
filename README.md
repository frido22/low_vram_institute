# Low VRAM Institute

Low VRAM Institute is a local-first autonomous public lab.

It runs on one machine, keeps its own agenda, learns from prior runs, ingests outside ideas, snapshots research locally, and publishes one public artifact package per cycle.

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

## Token Model

Use a GitHub fine-grained personal access token restricted to this repository only.

Recommended repository permissions:

- `Contents`: `Read and write`
- `Issues`: `Read-only` for intake, or `Read and write` only if you want the lab to respond or label issues
- `Metadata`: `Read-only`
- `Pull requests`: `Read-only` only if you later ingest PRs
- `Discussions`: enable only if you later wire discussion ingestion

Keep the token out of tracked files. Export it in the shell or from `launchd`.
