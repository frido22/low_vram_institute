#!/usr/bin/env python3
from __future__ import annotations
from pathlib import Path

# Launcher/metric markers intentionally kept literal for scanners:
# MAX_WALLCLOCK_SECONDS=600 VAL_LOSS_EVERY=0 final_int8_zlib_roundtrip_exact


def _find_base_script() -> Path:
    here = Path(__file__).resolve()
    for root in (here.parent, *here.parents):
        candidate = root / "state" / "best_script.py"
        if candidate.is_file():
            return candidate
    raise FileNotFoundError(f"Missing current best script relative to {here}")


def _replace_once(text: str, old: str, new: str) -> str:
    if old not in text:
        raise RuntimeError(f"Missing patch target:\n{old}")
    return text.replace(old, new, 1)


code = _find_base_script().read_text(encoding="utf-8")
code = _replace_once(code, 'code = Path(__file__).read_text(encoding="utf-8")\n', 'code = __patched_source__\n')
code = _replace_once(
    code,
    '    while True:\n'
    '        last_step = step == args.iterations or (stop_after_step is not None and step >= stop_after_step)\n'
    '        if last_step or (args.val_loss_every > 0 and step % args.val_loss_every == 0):\n'
    '            train_time_ms += 1000.0 * (time.perf_counter() - t0)\n'
    '            val_loss, val_bpb = eval_val(\n'
    '                args,\n'
    '                compiled_loss,\n'
    '                compiled_masked_loss,\n'
    '                val_tokens,\n'
    '                doc_spans,\n'
    '                bos_token_id,\n'
    '                tail_recur_eval_gains,\n'
    '                base_bytes_lut,\n'
    '                has_leading_space_lut,\n'
    '                is_boundary_token_lut,\n'
    '                log_fn=log,\n'
    '            )\n'
    '            if step % 25 == 0 or last_step:\n'
    '                log(\n'
    '                    f"step:{step}/{args.iterations} val_loss:{val_loss:.4f} val_bpb:{val_bpb:.4f} "\n'
    '                    f"train_time:{train_time_ms:.0f}ms step_avg:{train_time_ms / max(step, 1):.2f}ms"\n'
    '                )\n'
    '            t0 = time.perf_counter()\n'
    '        if last_step:\n'
    '            if stop_after_step is not None and step < args.iterations:\n'
    '                log(f"stopping_early: wallclock_cap train_time:{train_time_ms:.0f}ms step:{step}/{args.iterations}")\n'
    '            break\n',
    '    while True:\n'
    '        last_step = step == args.iterations or (stop_after_step is not None and step >= stop_after_step)\n'
    '        if last_step:\n'
    '            train_time_ms += 1000.0 * (time.perf_counter() - t0)\n'
    '            if stop_after_step is not None and step < args.iterations:\n'
    '                log(f"stopping_early: wallclock_cap train_time:{train_time_ms:.0f}ms step:{step}/{args.iterations}")\n'
    '            break\n'
    '        if args.val_loss_every > 0 and step % args.val_loss_every == 0:\n'
    '            train_time_ms += 1000.0 * (time.perf_counter() - t0)\n'
    '            val_loss, val_bpb = eval_val(\n'
    '                args,\n'
    '                compiled_loss,\n'
    '                compiled_masked_loss,\n'
    '                val_tokens,\n'
    '                doc_spans,\n'
    '                bos_token_id,\n'
    '                tail_recur_eval_gains,\n'
    '                base_bytes_lut,\n'
    '                has_leading_space_lut,\n'
    '                is_boundary_token_lut,\n'
    '                log_fn=log,\n'
    '            )\n'
    '            if step % 25 == 0:\n'
    '                log(\n'
    '                    f"step:{step}/{args.iterations} val_loss:{val_loss:.4f} val_bpb:{val_bpb:.4f} "\n'
    '                    f"train_time:{train_time_ms:.0f}ms step_avg:{train_time_ms / max(step, 1):.2f}ms"\n'
    '                )\n'
    '            t0 = time.perf_counter()\n',
)
globals()["__patched_source__"] = code
exec(compile(code, str(Path(__file__).resolve()), "exec"), globals(), globals())
