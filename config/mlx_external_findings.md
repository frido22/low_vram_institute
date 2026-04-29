Treat these as public upstream hypotheses from `openai/parameter-golf`, not as ground truth. Use them only when they fit a 600-second Apple Silicon run.

Competition target:
- This repo is competing on the 10-minute / 600-second Mac-mini official-like path, not unlimited-compute Mac demos.
- PRs with multi-hour or multi-day local training can be useful for motifs, but their reported scores are not comparable to this repo's runs.
- Do not chase CPU-only ternary, 40-hour EvoNAS, or post-train int6/GPTQ pipelines unless there is a small MLX transplant that can pay off inside one 600-second run.

High-signal transferable findings:
- PR `#1612` (`seekerPrice`): on local MLX `SP4096` at 5000 steps, softer small-batch hyperparameters beat H100-style defaults. Reported winning direction: `MATRIX_LR=0.02`, `MUON_MOMENTUM=0.95`, `MUON_MOMENTUM_WARMUP_START=0.90`, `QK_GAIN_INIT=4.0`. Transfer lesson: Mac local runs may prefer less aggressive matrix updates and less sharp attention than H100-tuned defaults.
- PR `#133`: shared-heavy / unique-light depth tying looked strong under matched local wallclock. Transfer lesson: parameter sharing, recurrence, or tied-depth variants are promising when they buy more useful updates per second.
- PR `#1627` (`mike-ferguson` EvoNAS): strongest MLX-related PR found. Reported `1.324649` on a non-record unlimited-compute run, but this came from ~40 hours of training to 10k steps plus post-train int6 GPTQ. The transferable part is not the long run or int6 pipeline; it is that search repeatedly favored `layer_traversal_mode = odds_then_evens`, `state_carryover = gated`, depth recurrence, and block sharing. Transfer lesson: for Mac-mini search, try small, compile-stable recurrent depth changes with learned carry gates and byte-aware sharing, but down-rank anything that depends on long training or post-train export tricks.
- PR `#1866` (`Trinity Ternary CPU v3`): reported `1.5042`, but it is CPU-only, 72 hours, ternary/base-3 packing, and a different training/export regime. Treat it as non-comparable to our 600-second MLX track. The only possible lesson is that compact low-bit packing can matter; do not spend daemon cycles on a full ternary rewrite here.
- PR `#1595` plus follow-up author comment: larger MLP allocation, more layers, and LeakyReLU-squared style activations showed small local MLX gains before being superseded by PR `#1612`. Transfer lesson: spending bytes on MLP capacity can help locally if quantization still behaves well, but hyperparameter tuning appears higher leverage.
- PR `#90`: reduced KV budget only mattered after export/quantization behavior for small matrices was fixed. Transfer lesson: parameter-count wins are irrelevant unless final compressed artifact bytes also improve.
- PR `#97`: deeper, narrower local models beat an early baseline in capped MLX tests. Transfer lesson: depth-for-width swaps remain worth testing, but only on the exact final quantized metric.

Useful priority order for Mac-mini search:
- Highest priority: PR `#1612` hyperparameters.
- Next: PR `#133` shared-heavy / unique-light depth ideas.
- Then: a minimal gated-recurrence transplant inspired by PR `#1627`, without copying its long-run or int6 path.
- Lower priority: MLP-capacity shifts from PR `#1595` and early depth-for-width ideas from PR `#97`.

Deprioritized or non-transferable findings:
- CPU-only or multi-day Mac results are non-comparable to this repo's goal. They should not outrank clean 600-second MLX evidence.
- PR `#1183` (`Retrodiction`, reported `1.508` on M1 Max) was later closed by the author as superseded by PR `#1255`, and the author explicitly described the retrodiction line as a documented negative result there. Do not prioritize retrodiction for this repo.
- PR `#877` (`sin^2` activation plus screening pipeline) showed only small local screening signal for the activation itself. Treat activation swaps as a low-priority micro-ablation, not a main search direction.
- PR `#983` (`11L LeakyReLU^2 + EMA + Int6`) did not report an actual validated `val_bpb`; it is an architecture proposal awaiting H100 validation. Do not treat it as evidence of a winning local Mac direction.

Actionable EvoNAS transplant ideas for this repo:
- Favor a minimal recurrence transplant over a full architecture rewrite. Example direction: repeat one or two late blocks once more with shared weights.
- If recurrence is added, prefer a learned scalar or vector gate on the carry path instead of a bare residual add. The goal is controlled reuse, not just more depth.
- Treat `odds_then_evens` as inspiration, not a requirement. Only try a traversal change if it can be implemented with fixed shapes and no compile churn.
- Do not chase PR `#1627`'s post-train int6 path here. This repo scores itself on the final exact `int8+zlib` roundtrip, so architectural wins matter more than alternate export pipelines.
- Any recurrence/sharing experiment must preserve the current strengths of this repo: exact final eval, stable 600-second stop behavior, and compact compressed artifact size.

Recommended experiment order from PR `#1627`:
- First: add a tiny gated recurrence on deep blocks while keeping current quant-aware endgame unchanged.
- Second: test lightweight block sharing or tied tail blocks only if the first recurrence transplant is promising.
- Third: only then consider traversal-order experiments, because they are more invasive and may create MLX compile overhead.

Current official leaderboard motifs worth borrowing carefully:
- The merged H100 leaderboard is dominated by recurrence, parallel residuals, stronger tokenizers, and TTT-style evaluation tricks.
- For this repo, recurrence and simple residual-path changes may transfer; H100-only systems tricks and expensive TTT variants usually should not dominate Mac-mini search.

Planner use policy:
- Prefer one transplant at a time so local attribution stays clear.
- Favor ideas that are cheap to test under exact final evaluation.
- If an external idea needs multi-hour training, long CUDA runs, or a different tokenizer stack, down-rank it unless there is a minimal local proxy.
