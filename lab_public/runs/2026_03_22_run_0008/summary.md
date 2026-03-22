# 2026_03_22_run_0008

## What was tried
Replay Muon Momentum 0.99 On Top Of Validated WD 0.04

## Why it was tried
The best stable result came from Muon matrix weight decay 0.04 with momentum 0.99, while the latest mixed-quantization follow-up was flat. The highest-value next run is a clean replay of the strongest validated training-side change, to confirm it remains the best official-like config before promoting or branching further.

## Main result
- Score: 9.2520
- Runtime: 1410.48s
- Passed: True
- Needs validation: False

## Logging focus
- stability
- score
- wallclock

## What changed
`parameter_golf` adapter run for mode `validate`.

## Belief update
Ran local MLX Parameter Golf in official-like mode on the Mac mini. Final val_bpb=9.2520, val_loss=15.6264, quantized artifact=5058316 bytes. Code patch applied (1 edits). Score=9.2520. Expected signal: If 0.99 momentum is genuinely robust on this hardware and code path, val_bpb should land back near 9.2505 or better with similar wallclock usage; if it regresses, the prior gain was likely run noise.

## What next
If 0.99 momentum is genuinely robust on this hardware and code path, val_bpb should land back near 9.2505 or better with similar wallclock usage; if it regresses, the prior gain was likely run noise.
