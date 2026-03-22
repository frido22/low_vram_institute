# 2026_03_22_run_0001

## What was tried
Muon Weight Decay 0.04

## Why it was tried
No prior runs exist, so start with a single upstream-inspired delta that is cheap to test and easy to attribute. The upstream notes and leaderboard repeatedly point to weight decay for quantization, often with Muon WD=0.04. This script currently has no weight decay at all, so adding Muon-only decay is a clean first probe that preserves the baseline architecture and 600s budget while targeting post-quantization robustness.

## Main result
- Score: 9.2640
- Runtime: 1413.97s
- Passed: True
- Needs validation: True

## Logging focus
- upstream_tactic
- score_delta
- wallclock

## What changed
`parameter_golf` adapter run for mode `explore`.

## Belief update
Ran local MLX Parameter Golf in official-like mode on the Mac mini. Final val_bpb=9.2640, val_loss=15.6467, quantized artifact=5050855 bytes. Code patch applied (2 edits). Score=9.2640. Expected signal: If quantization-aware regularization matters here, final_int8_zlib_roundtrip_exact val_bpb should improve versus the untouched baseline without changing artifact rules or eval behavior. A flat or worse result would argue against spending more search budget on optimizer regularization before trying architecture/eval changes.

## What next
If quantization-aware regularization matters here, final_int8_zlib_roundtrip_exact val_bpb should improve versus the untouched baseline without changing artifact rules or eval behavior. A flat or worse result would argue against spending more search budget on optimizer regularization before trying architecture/eval changes.
