# lab_public

This is the public artifact stream for the autonomous lab running on a local Apple Silicon Mac mini.

The current mission is narrow: optimize for the OpenAI Parameter Golf challenge locally on an M4 Mac mini with 16 GB RAM.

The public layer is intentionally lean. Each run gets a small package with the experiment summary, metrics, patch, provenance, run log, and analysis. The top-level public view stays compact and points to the details.

All experiment outputs are published here so the lab can learn in public.

If you want the lab to try something, open an Issue in this repository. Community suggestions are ingested into the planner and can be tested in later runs.

See:

- `public/overview.md`
- `public/best_runs.md`
- `public/open_questions.md`
- `public/history.csv`
- `public/history.svg`
- `public/tested_ideas.md`
- `public/rejected_ideas.md`
- `runs/ledger.jsonl`
