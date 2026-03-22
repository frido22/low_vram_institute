# 2026_03_22_run_0020

## What was tried
Reproduce the current upstream best candidate on the official M4 validation path

## Why it was tried
Plateau has reached 2 with recent validate runs flat, so the next useful step is research rather than another confirmation pass. The strongest new lead is the queued upstream-related candidate (`github:4114281267`), and testing it through the real upstream code path on the official validation split keeps procedure close to the challenge while isolating the only intended mismatch: M4 hardware.

## Main result
- Score: 2.2943
- Runtime: 180.99s
- Passed: True
- Needs validation: True

## Logging focus
- upstream parity
- validation split fidelity
- runtime under 10-minute cap

## What changed
`parameter_golf` adapter run for mode `research`.

## Belief update
Ran local MLX Parameter Golf in official-like mode on the Mac mini. Final val_bpb=2.2943, val_loss=3.8751, quantized artifact=10255595 bytes. Score=2.2943. Expected signal: A single capped 10-minute upstream run either beats ~2.2933 on M4 or cleanly shows no gain versus the validated baseline, giving a concrete next branch.

## What next
A single capped 10-minute upstream run either beats ~2.2933 on M4 or cleanly shows no gain versus the validated baseline, giving a concrete next branch.
