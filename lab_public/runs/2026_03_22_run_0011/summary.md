# 2026_03_22_run_0011

## What was tried
Re-run the new local best once on the official-like M4 path to confirm the int5-funded 10th-layer plus BigramHash(10240) gain under the 10-minute cap

## Why it was tried
The last run was a community-sourced improvement to a new best score (2.29234832) and is still marked needs_validation. Plateau count is 0, so there is no reason to branch into research; the clean next step is to confirm the win on the same upstream-like code path, split, and wallclock cap before promoting it.

## Main result
- Score: 2.2939
- Runtime: 180.30s
- Passed: True
- Needs validation: False

## Logging focus
- validation stability
- wallclock cap compliance
- official-like reproducibility

## What changed
`parameter_golf` adapter run for mode `validate`.

## Belief update
Ran local MLX Parameter Golf in official-like mode on the Mac mini. Final val_bpb=2.2939, val_loss=3.8743, quantized artifact=10263096 bytes. Score=2.2939. Expected signal: A second pass should land near the new best on the same official-split mixed-quant recipe; confirmation supports treating this recipe as the current stable local leader, while a clear regression would mark the win as noisy.

## What next
A second pass should land near the new best on the same official-split mixed-quant recipe; confirmation supports treating this recipe as the current stable local leader, while a clear regression would mark the win as noisy.
