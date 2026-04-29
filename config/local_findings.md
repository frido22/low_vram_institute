Treat these as empirical findings from this repo's own Mac-mini runs, not as broad truths.

Current local anchor:
- The best valid run is `2026_04_23_run_0031` at `1.51562813`. That is the reference branch to build from.
- The best region is still the compact `9x512` recurrent-tail family with reverse tail traversal, anchored carry/skip structure, quant-aware endgame, and a near-cap export budget around `15.75 MB`.
- Recent close runs stayed in the same family: `2026_04_23_run_0029` at `1.51642875`, `2026_04_23_run_0095` at `1.51643298`, `2026_04_24_run_0010` at `1.51681634`, `2026_04_23_run_0102` at `1.51686560`, `2026_04_23_run_0094` at `1.51689159`, and `2026_04_24_run_0004` at `1.51686713`.

High-confidence local negatives:
- Pure SeekerPrice / PR `#1612` hyperparameter transplants have not paid off here. Do not keep spending runs on near-verbatim hyperparameter copies.
- Squeezed output-head families have consistently missed. Extra output-head capacity and large underfilled artifacts were not the bottleneck.
- Larger update granularity, larger eval-batch changes, and broad nearby-shape churn did not beat the current best. Use them rarely.
- Current planner waste pattern: overlong scripts. Plans that exceed the `1500` line limit are rejected before launch. Avoid ideas that need broad file growth.
- Recent `2026_04_29` runs around `2.05` BPB are not useful evidence about the architecture. They enabled intermediate validation, stopped around step `51`, and spent the wallclock budget before real training. Keep `VAL_LOSS_EVERY=0` and preserve the final exact eval only.

Medium-confidence local lessons:
- Small control tweaks can get close, but they have plateaued. Do not let LR, batch, reserve, or seed sweeps dominate the queue.
- The best region is close to the size cap. Byte reallocations should support the recurrent-tail/export path, not create unused headroom.
- Generic "Refine current best" runs sometimes won because the baseline family is strong, but repeated no-op refinements should not crowd out real hypotheses.

What still looks promising:
- Reverse-tail anchor variants remain the best non-generic signal. `Reverse Tail Anchor Refresh` and `Reverse Tail Anchor Mix` got close enough to justify nearby compact variants.
- Recurrent-tail float rescue also remains live. `Dual Recurrent-Tail V FP16 Rescue` and `Recurrent-Exit Value FP16 Reallocation` were close misses.
- Recurrence scheduling and curricula are still worth trying if they stay compile-stable and compact.
- Tail float-budget reallocation is still promising if it directly supports the winning recurrent-tail path rather than funding separate heads.

Planner bias from these runs:
- Default to creative but compact structural edits on top of the `0031` recurrent-tail baseline.
- Down-rank repeated hyperparameter-only sweeps, output-head-only expansions, large batch/eval perturbations, and file-bloating rewrites.
- Reject plans that add intermediate validation, early tiny iteration caps, or any scoring proxy that prevents a normal 700+ step Mac-mini training run.
- Prioritize comparability: 600-second MLX, same data/tokenizer path, same final int8+zlib exact metric. Do not let long-run Apple Silicon submissions redefine the target.
- If a planned run needs many new helpers, simplify the existing script first or choose a smaller hypothesis.
