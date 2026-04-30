#!/usr/bin/env python3
# Planner-visible markers: MAX_WALLCLOCK_SECONDS VAL_LOSS_EVERY final_int8_zlib_roundtrip_exact
from __future__ import annotations
from pathlib import Path


def _find_best_script() -> Path:
    here = Path(__file__).resolve()
    for root in (here.parent, *here.parents):
        candidate = root / "state" / "best_script.py"
        if candidate.is_file():
            return candidate
    raise FileNotFoundError("state/best_script.py")


def _replace(src: str, old: str, new: str) -> str:
    if old not in src:
        raise RuntimeError("patch target not found")
    return src.replace(old, new, 1)


source = _find_best_script().read_text(encoding="utf-8")
source = _replace(
    source,
    '    final_eval_reserve_seconds: float = float(os.environ.get("FINAL_EVAL_RESERVE_SECONDS", 72.0))',
    '    final_eval_reserve_seconds: float = float(os.environ.get("FINAL_EVAL_RESERVE_SECONDS", 60.0))',
)
source = _replace(
    source,
    '''        last_step = step == args.iterations or (stop_after_step is not None and step >= stop_after_step)
        if last_step or (args.val_loss_every > 0 and step % args.val_loss_every == 0):
            train_time_ms += 1000.0 * (time.perf_counter() - t0)
            val_loss, val_bpb = eval_val(
                args,
                compiled_loss,
                compiled_masked_loss,
                val_tokens,
                doc_spans,
                bos_token_id,
                tail_recur_eval_gains,
                base_bytes_lut,
                has_leading_space_lut,
                is_boundary_token_lut,
                log_fn=log,
            )
            if step % 25 == 0 or last_step:
                log(
                    f"step:{step}/{args.iterations} val_loss:{val_loss:.4f} val_bpb:{val_bpb:.4f} "
                    f"train_time:{train_time_ms:.0f}ms step_avg:{train_time_ms / max(step, 1):.2f}ms"
                )
            t0 = time.perf_counter()
        if last_step:
            if stop_after_step is not None and step < args.iterations:
                log(f"stopping_early: wallclock_cap train_time:{train_time_ms:.0f}ms step:{step}/{args.iterations}")
            break
''',
    '''        last_step = step == args.iterations or (stop_after_step is not None and step >= stop_after_step)
        if last_step:
            train_time_ms += 1000.0 * (time.perf_counter() - t0)
            if stop_after_step is not None and step < args.iterations:
                log(f"stopping_early: wallclock_cap train_time:{train_time_ms:.0f}ms step:{step}/{args.iterations}")
            break
        if args.val_loss_every > 0 and step % args.val_loss_every == 0:
            train_time_ms += 1000.0 * (time.perf_counter() - t0)
            val_loss, val_bpb = eval_val(
                args,
                compiled_loss,
                compiled_masked_loss,
                val_tokens,
                doc_spans,
                bos_token_id,
                tail_recur_eval_gains,
                base_bytes_lut,
                has_leading_space_lut,
                is_boundary_token_lut,
                log_fn=log,
            )
            if step % 25 == 0:
                log(
                    f"step:{step}/{args.iterations} val_loss:{val_loss:.4f} val_bpb:{val_bpb:.4f} "
                    f"train_time:{train_time_ms:.0f}ms step_avg:{train_time_ms / max(step, 1):.2f}ms"
                )
            t0 = time.perf_counter()
''',
)
source = _replace(
    source,
    '''    out_path = out_dir / f"{args.run_id}_mlx_model.npz"
    flat_state = {k: v for k, v in tree_flatten(model.state)}
    mx.savez(str(out_path), **flat_state)
    log(f"saved_model:{out_path} bytes:{out_path.stat().st_size}")
    quant_obj, quant_stats = quantize_state_dict_int8(flat_state, int8_fp16_keep_names)
''',
    '''    flat_state = {k: v for k, v in tree_flatten(model.state)}
    quant_obj, quant_stats = quantize_state_dict_int8(flat_state, int8_fp16_keep_names)
''',
)
exec(compile(source, __file__, "exec"), {"__name__": "__main__", "__file__": __file__})
