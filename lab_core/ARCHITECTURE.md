# Architecture

## System Shape

The system is split into two domains:

- `lab_core`: private control plane
- `lab_public`: append-only public artifact store

`lab_core` is responsible for boring reliability. The supervisor owns retries, resume logic, health checks, heartbeats, and one-run-at-a-time guarantees. The planner chooses the next action. The executor applies the action through an experiment adapter. The evaluator normalizes metrics. The publisher writes public artifacts and updates the public narrative.

## Lifecycle

1. Supervisor acquires the persistent lock and validates disk and repo health.
2. Research snapshots and community intake are refreshed from local deterministic sources.
3. Planner reads durable state, recent runs, queued ideas, research notes, and community suggestions.
4. Planner selects one mode and one action.
5. Executor snapshots state, runs the chosen adapter, captures logs, and evaluates the outcome.
6. State store updates local memory and checkpoints each stage.
7. Publisher appends a ledger row, writes a run package, updates the lean public overview pages, and records contributor credit when relevant.
8. Supervisor clears transient state, updates heartbeats, and schedules the next cycle with backoff on failure.

## Reliability Model

- Single-run lock file in `state/run.lock`
- Checkpoints in `state/checkpoint.json`
- Heartbeats in `logs/heartbeat.json`
- Append-only events in `logs/events.jsonl`
- Crash recovery based on durable checkpoints and last successful stage
- Transient failure backoff with bounded exponential delays
- Refusal to proceed if free disk drops below configured threshold or required directories are missing

## Research And Community

The research pipeline is local-first. It fetches configured sources to disk and stores normalized text snapshots plus metadata. The GitHub intake service reads issue/discussion exports or snapshots and converts them into normalized queue entries. The planner treats these as inputs, not commands.

## Public Identity

Every cycle updates:

- `lab_public/runs/<run_id>/summary.md`
- `lab_public/runs/<run_id>/metrics.json`
- `lab_public/runs/<run_id>/metrics.jsonl`
- `lab_public/runs/<run_id>/run.log`
- `lab_public/runs/<run_id>/analysis.md`
- `lab_public/runs/<run_id>/diff.patch`
- `lab_public/runs/<run_id>/provenance.json`
- `lab_public/runs/ledger.jsonl`
- `lab_public/public/overview.md`
- `lab_public/public/best_runs.md`
- `lab_public/public/open_questions.md`
- `lab_public/public/history.svg`
- `lab_public/public/tested_ideas.md`
- `lab_public/public/rejected_ideas.md`

The public repo is intended to feel alive without becoming noisy. The README stays high-level. The lean overview pages point to the rolling run packages where the full narrative lives.
