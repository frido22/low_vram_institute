# 2026_03_22_run_0018

## What was tried
Probe Offset-Averaged Sliding Validation

## Why it was tried
The best local line is still the tied-embedding bigram-residual family, but the latest validation replay came back flat and plateau_count is now 1. Upstream records repeatedly use sliding-window evaluation, while the current MLX script still scores only non-overlapping 1024-token windows. This run tests one upstream-inspired eval change only: average validation over two sequence alignments by default (stride 512). That keeps the official validation split, final roundtrip eval, and 600s training cap intact while checking whether our current scorer is underestimating strong runs because of boundary sensitivity.

## Main result
- Score: 9.2565
- Runtime: 1419.61s
- Passed: True
- Needs validation: True

## Logging focus
- val_bpb
- eval_alignment
- quantized_roundtrip

## What changed
`parameter_golf` adapter run for mode `research`.

## Belief update
Ran local MLX Parameter Golf in official-like mode on the Mac mini. Final val_bpb=9.2565, val_loss=15.6334, quantized artifact=5058388 bytes. Code patch applied (2 edits). Score=9.2565. Expected signal: A real signal is a lower final_int8_zlib_roundtrip_exact val_bpb than the current validated band (~5.866) with stable quantized-roundtrip behavior. If the score is flat or worse, eval-only alignment tweaks are probably not the next bottleneck on this Mac path.

## What next
A real signal is a lower final_int8_zlib_roundtrip_exact val_bpb than the current validated band (~5.866) with stable quantized-roundtrip behavior. If the score is flat or worse, eval-only alignment tweaks are probably not the next bottleneck on this Mac path.
