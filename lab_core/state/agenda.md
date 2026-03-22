# Agenda

- Current mode bias: exploit
- Latest expected signal: A cleaner lower val_bpb than 2.2944445 from the same upstream-local baseline path, with runtime still inside the 10-minute wallclock cap. Even a modest improvement would confirm the local stack is sensitive to known upstream tactics.
- Next public update focus: Use the real upstream training/eval path with the official FineWeb validation split and preserve the 10-minute wallclock cap., Test exactly one concrete tactic next: sliding-window evaluation, without mixing in extra architecture or quantization changes., Treat the M4/16GB machine as the only mismatch; avoid local-only shortcuts that break comparability., If the run improves cleanly, queue a confirmatory rerun next; if not, move to the next single upstream tactic rather than branching widely.
