# 2026_03_22_run_0014

## What was tried
Isolate SWA start_frac=0.4 alone on the validated 10L int5-MLP + BigramHash(10240) official-split path under the 10-minute M4 cap

## Why it was tried
Plateau count is 3, so another broad exploit run is poorly justified. The only recent upstream-inspired addition tested after the local best was the combined SWA+WD bundle, and it regressed from 2.29234832 to 2.2966215, so attribution is still unresolved. Upstream notes claim SWA is the larger delta while WD is marginal, so the clean next step is to isolate SWA alone on the validated winner and keep the official code path, validation split, and wallclock cap unchanged.

## Main result
- Score: 2.2945
- Runtime: 180.76s
- Passed: True
- Needs validation: True

## Logging focus
- ablation clarity
- wallclock parity
- official-path fidelity

## What changed
`parameter_golf` adapter run for mode `research`.

## Belief update
Ran local MLX Parameter Golf in official-like mode on the Mac mini. Final val_bpb=2.2945, val_loss=3.8754, quantized artifact=10260112 bytes. Score=2.2945. Expected signal: A pass that beats or matches 2.29234832 would identify SWA as the remaining transferable upstream tactic; another clear regression would let us demote SWA and stop spending exploit budget on that branch.

## What next
A pass that beats or matches 2.29234832 would identify SWA as the remaining transferable upstream tactic; another clear regression would let us demote SWA and stop spending exploit budget on that branch.
