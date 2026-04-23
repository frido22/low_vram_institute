Treat these as empirical findings from this repo's own Mac-mini runs, not as broad truths.

Current local anchor:
- The best valid run is now `2026_04_23_run_0086` at `1.51703477`. It is the reference branch to build from.
- The winning local family is still the compact `9x512` recurrent-tail line with quant-aware endgame, reverse recurrent-tail traversal, decoder-output carry anchoring, aligned decoder skips, and tail float rescue. Do not abandon that baseline casually.
- Recent close runs in the same family include `2026_04_23_run_0083` at `1.51755543` and `2026_04_23_run_0087` at `1.51906250`. This family is real, but endless near-identical replays should not dominate the queue.

High-confidence local negatives:
- Pure SeekerPrice / PR `#1612` hyperparameter transplants have not paid off here. Recent example: `2026_04_21_run_0061` scored `1.531726`. Earlier PR1612-style transplants also missed or went invalid. Do not keep spending runs on near-verbatim hyperparameter copies.
- Squeezed output-head families have consistently missed. Rank-64 and rank-128 untied output heads, even when float-kept and well under the size cap, have not beaten the recurrent-tail best. Recent example: `2026_04_21_run_0060` scored `1.53019896` at only `14.84 MB`. Lesson: unused byte headroom alone is not enough; extra output-head capacity has not been the bottleneck.
- Larger update granularity and larger eval-batch changes were bad. `2026_04_21_run_0063` (`Five-Sequence Updates With Larger Eval Batch`) both scored poorly and exceeded the size cap. Avoid this direction.
- Nearby shape churn can be viable but was not enough by itself. `2026_04_21_run_0064` (`10x480`) was legal but weaker at `1.54351512`. Treat neighboring shapes as occasional probes, not the default queue.

Medium-confidence local lessons:
- Small optimizer/control tweaks can move the score but have recently plateaued. `2026_04_21_run_0062` (`Fast Control LR Split`) was the closest recent miss at `1.524813`, but still clearly behind the best. Use control sweeps sparingly; they should not dominate the queue.
- Aggressive byte squeezing that reduces recurrence depth has not paid off. Single-recurrence + output-head branches stayed small and fast but lost too much quality. The recurrent-tail budget itself appears valuable.
- The best region is already close to the size cap. Runs around `15.7 MB` have been stronger than very underfilled `14.6–14.9 MB` artifacts. Prefer byte reallocations that preserve strong tail structure over arbitrary unused headroom.
- Generic "Refine current best" runs unexpectedly produced a new best in `0086`, likely because the current branch is strong and run-to-run variance still matters. Use this as evidence that the baseline is strong, not as permission to run infinite identical scripts.

What remains worth trying:
- Traversal-order changes have shown promise through the current reverse-order recurrent-tail family. Further variants should be compile-stable and targeted, not broad rewrites.
- Recurrence scheduling / curricula are still underexplored locally. Try recurrence activation schedules or phase-based recurrence depth before more small LR tweaks.
- Tail float-budget reallocation is still promising if it directly supports the winning recurrent-tail path rather than funding separate heads.
- If trying a bigger structural idea, it should preserve the current strengths: exact final eval, stable 600s stop behavior, recurrent tail quality, and compact export.
- Late validation-aligned loss masking, token-class conditional output bias, and greedy fp16 keep selection remain underexplored enough to justify one or two serious runs each if implemented cleanly.

Planner bias from these runs:
- Default to creative but compile-stable structural changes on top of the best recurrent-tail baseline.
- Down-rank repeated tiny hyperparameter sweeps, repeated output-head-only expansions, and large batch/eval-control perturbations.
- When using extra bytes, spend them on the proven recurrent-tail / export path before funding new side heads.
- If a planned run is only a seed/LR/batch/reserve tweak, replace it with a structural hypothesis unless there is a specific local result motivating that exact tweak.
