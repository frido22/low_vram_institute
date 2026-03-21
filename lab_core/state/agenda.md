# Agenda

- Current mode bias: exploit
- Latest expected signal: A real improvement would appear as a small but repeatable score increase over 0.61 across at least two local MLX reruns of the same candidate; otherwise the signal is that current variance dominates and the search space should stay narrow.
- Next public update focus: Freeze the current best local MLX baseline as the control and record its exact hyperparameters and runtime footprint on the M4/16GB machine., Run a narrow sweep around only 3-5 local knobs with small deltas, prioritizing settings that affect throughput and stability on MLX rather than remote-GPU-only ideas., Promote a candidate only if it beats 0.61 twice locally under the same evaluation path; otherwise discard it as noise and keep the control.
