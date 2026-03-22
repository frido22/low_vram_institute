# Runtime State

This directory is local runtime state for the daemon.

These files are intentionally not tracked in git. They are machine memory, checkpoints, queues, and rolling notes for the local process.

The public truth lives under `lab_public/`. The durable local truth for the running daemon is regenerated here as the lab runs.
