# State

Tracked state:

- `ledger.jsonl` — append-only run history
- `best_script.py` — current best valid script
- `best_diff.patch` — diff for the current best script

Transient state:

- `next_plan.md` — prepared next plan
- `pending_plan.md` — plan for the currently assigned run id
- `run.lock` — active run lock
- `planner.lock` — active background planner lock

State is committed with publishes so the lab can resume from the latest pushed search state.
