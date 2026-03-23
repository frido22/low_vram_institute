# Output

Published artifacts from the autonomous lab.

- `reports/history.csv` — `final_val_bpb` history
- `reports/history.svg` — best valid `final_val_bpb` chart
- `runs/<run_id>/` — per-run artifacts (`README.md`, `submission.json`, `artifact_size.json`, `train_gpt_mlx.py`, `diff.patch`, `run.log`, optional `requirements.txt`, optional quantized model file`)

`run.log` contains the raw Parameter Golf training log, including step logs, warnings, throughput, memory, and final exact metrics.
