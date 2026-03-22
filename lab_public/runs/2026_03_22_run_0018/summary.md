# 2026_03_22_run_0018

## What was tried
Queue the public validation-policy idea and test whether it improves promotion discipline without changing the upstream eval path

## Why it was tried
A fresh validate run already improved and passed on 2026_03_22_run_0017, so immediate re-validation is lower value. Plateau count is 0, so research is premature. Community item `github:101` passes a basic smell check because it recommends validating top candidates twice before promotion, which matches the strongest recent signal and keeps the procedure close to the official path.

## Main result
- Score: 2.2934
- Runtime: 180.74s
- Passed: True
- Needs validation: True

## Logging focus
- upstream-faithfulness
- repeatability
- promotion-criteria

## What changed
`parameter_golf` adapter run for mode `community`.

## Belief update
Ran local MLX Parameter Golf in official-like mode on the Mac mini. Final val_bpb=2.2934, val_loss=3.8735, quantized artifact=10259973 bytes. Score=2.2934. Expected signal: The run should confirm that candidate promotion decisions remain stable when constrained to repeated upstream validation on the official split under the 10-minute cap, with no score regression beyond normal run-to-run noise.

## What next
The run should confirm that candidate promotion decisions remain stable when constrained to repeated upstream validation on the official split under the 10-minute cap, with no score regression beyond normal run-to-run noise.
