# Agenda

- Current mode bias: exploit
- Latest expected signal: A real exploit win is a lower official-split val_bpb than 2.29350473 under the same 10-minute wallclock cap, with the upstream code path preserved except for adding bigram features on top of the validated mixed-quantization sliding-window setup.
- Next public update focus: Keep hardware and procedure fixed: Apple Silicon M4, official validation split, real upstream path, 10-minute cap., Use the validated mixed-quantization plus sliding-window configuration as the exact control., Test one change only: add upstream-style bigram features, then compare val_bpb against 2.29350473., Promote only if the run passes cleanly and beats the current best; otherwise record as a non-improving exploit and move on.
