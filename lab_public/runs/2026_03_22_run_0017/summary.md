# 2026_03_22_run_0017

## What was tried
Re-run official baseline twice on the upstream validation path

## Why it was tried
Last run 2026_03_22_run_0016 set a new best score of 2.29645359 and is explicitly marked needs_validation. Plateau count is 0, so this is not a research moment. The clean next step is confirmation on the real upstream path, official validation split, and 10-minute cap, with hardware mismatch held constant.

## Main result
- Score: 2.2933
- Runtime: 180.77s
- Passed: True
- Needs validation: False

## Logging focus
- upstream parity
- score stability
- runtime under cap

## What changed
`parameter_golf` adapter run for mode `validate`.

## Belief update
Ran local MLX Parameter Golf in official-like mode on the Mac mini. Final val_bpb=2.2933, val_loss=3.8733, quantized artifact=10259708 bytes. Score=2.2933. Expected signal: Two repeat runs on the official upstream validation flow stay near 2.2965 within normal variance and pass the 10-minute cap on the M4 Mac mini.

## What next
Two repeat runs on the official upstream validation flow stay near 2.2965 within normal variance and pass the 10-minute cap on the M4 Mac mini.
