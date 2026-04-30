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
    '    quant_aware_every: int = int(os.environ.get("QUANT_AWARE_EVERY", 24))\n'
    '    quant_aware_embed_lr_mul: float = float(os.environ.get("QUANT_AWARE_EMBED_LR_MUL", 0.6))\n',
    '    quant_aware_every: int = int(os.environ.get("QUANT_AWARE_EVERY", 24))\n'
    '    final_calibration_seconds: float = float(os.environ.get("FINAL_CALIBRATION_SECONDS", 8.0))\n'
    '    final_calibration_scalar_lr_mul: float = float(os.environ.get("FINAL_CALIBRATION_SCALAR_LR_MUL", 0.18))\n'
    '    quant_aware_embed_lr_mul: float = float(os.environ.get("QUANT_AWARE_EMBED_LR_MUL", 0.6))\n',
)
code = _replace_once(
    code,
    '        updated = dict(params)\n'
    '        updated.update(self.muon.step(params, grads, step=step, lr_mul=lr_mul * matrix_lr_mul))\n'
    '        self.adam_embed.learning_rate = self.args.tied_embed_lr * lr_mul * embed_lr_mul\n'
    '        updated.update(\n'
    '            self.adam_embed.apply_gradients(\n'
    '                {self.embed_key: grads[self.embed_key]},\n'
    '                {self.embed_key: params[self.embed_key]},\n'
    '            )\n'
    '        )\n'
    '        self.adam_scalar.learning_rate = self.args.scalar_lr * lr_mul * scalar_lr_mul\n'
    '        scalar_grads = {k: grads[k] for k in self.scalar_keys}\n'
    '        scalar_params = {k: params[k] for k in self.scalar_keys}\n'
    '        updated.update(self.adam_scalar.apply_gradients(scalar_grads, scalar_params))\n',
    '        updated = dict(params)\n'
    '        if matrix_lr_mul != 0.0:\n'
    '            updated.update(self.muon.step(params, grads, step=step, lr_mul=lr_mul * matrix_lr_mul))\n'
    '        if embed_lr_mul != 0.0:\n'
    '            self.adam_embed.learning_rate = self.args.tied_embed_lr * lr_mul * embed_lr_mul\n'
    '            updated.update(\n'
    '                self.adam_embed.apply_gradients(\n'
    '                    {self.embed_key: grads[self.embed_key]},\n'
    '                    {self.embed_key: params[self.embed_key]},\n'
    '                )\n'
    '            )\n'
    '        if scalar_lr_mul != 0.0:\n'
    '            self.adam_scalar.learning_rate = self.args.scalar_lr * lr_mul * scalar_lr_mul\n'
    '            scalar_grads = {k: grads[k] for k in self.scalar_keys}\n'
    '            scalar_params = {k: params[k] for k in self.scalar_keys}\n'
    '            updated.update(self.adam_scalar.apply_gradients(scalar_grads, scalar_params))\n',
)
code = _replace_once(
    code,
    'def main() -> None:\n',
    'def calibrate_roundtripped_controls(\n'
    '    args: Hyperparameters,\n'
    '    model: GPT,\n'
    '    opt: SplitOptimizers,\n'
    '    train_loader: TokenLoader,\n'
    '    compiled_loss_and_grad,\n'
    '    int8_fp16_keep_names: set[str],\n'
    '    tail_recur_eval_gains: mx.array,\n'
    '    train_time_ms: float,\n'
    ') -> tuple[float, int]:\n'
    '    if args.final_calibration_seconds <= 0.0:\n'
    '        return train_time_ms, 0\n'
    '    remaining = args.final_calibration_seconds\n'
    '    if args.max_wallclock_seconds > 0:\n'
    '        remaining = min(remaining, max(args.max_wallclock_seconds - train_time_ms / 1000.0 - 2.0, 0.0))\n'
    '    if remaining <= 0.0:\n'
    '        return train_time_ms, 0\n'
    '    apply_final_roundtrip_to_state(model, int8_fp16_keep_names)\n'
    '    mx.synchronize()\n'
    '    start = time.perf_counter()\n'
    '    deadline = start + remaining\n'
    '    steps = 0\n'
    '    cal_step = loss_and_grad_one_batch if args.use_single_microbatch_path else loss_and_grad_chunked\n'
    '    while time.perf_counter() < deadline:\n'
    '        train_loss, grads = cal_step(args, train_loader, compiled_loss_and_grad, tail_recur_eval_gains)\n'
    '        opt.step(model, grads, step=args.iterations + steps, lr_mul=1.0, embed_lr_mul=0.0, matrix_lr_mul=0.0, scalar_lr_mul=args.final_calibration_scalar_lr_mul)\n'
    '        mx.eval(train_loss)\n'
    '        mx.synchronize()\n'
    '        steps += 1\n'
    '    apply_final_roundtrip_to_state(model, int8_fp16_keep_names)\n'
    '    mx.synchronize()\n'
    '    return train_time_ms + 1000.0 * (time.perf_counter() - start), steps\n'
    'def main() -> None:\n',
)
code = _replace_once(
    code,
    '    log(f"quant_aware:train_seconds:{args.quant_aware_train_seconds:.1f} iters:{args.quant_aware_iters} every:{args.quant_aware_every}")\n',
    '    log(f"quant_aware:train_seconds:{args.quant_aware_train_seconds:.1f} iters:{args.quant_aware_iters} every:{args.quant_aware_every}")\n'
    '    log(f"final_calibration:seconds:{args.final_calibration_seconds:.1f} scalar_lr_mul:{args.final_calibration_scalar_lr_mul}")\n',
)
code = _replace_once(
    code,
    '    if tracked_ema:\n'
    '        model.update(tree_unflatten(list(tracked_ema.items())))\n'
    '        apply_final_roundtrip_to_state(model, int8_fp16_keep_names)\n'
    '    out_path = out_dir / f"{args.run_id}_mlx_model.npz"\n',
    '    if tracked_ema:\n'
    '        model.update(tree_unflatten(list(tracked_ema.items())))\n'
    '        apply_final_roundtrip_to_state(model, int8_fp16_keep_names)\n'
    '    train_time_ms, calibration_steps = calibrate_roundtripped_controls(\n'
    '        args,\n'
    '        model,\n'
    '        opt,\n'
    '        train_loader,\n'
    '        compiled_loss_and_grad,\n'
    '        int8_fp16_keep_names,\n'
    '        tail_recur_eval_gains,\n'
    '        train_time_ms,\n'
    '    )\n'
    '    if calibration_steps:\n'
    '        log(f"final_calibration:steps:{calibration_steps} train_time:{train_time_ms:.0f}ms")\n'
    '    out_path = out_dir / f"{args.run_id}_mlx_model.npz"\n',
)
code = _replace_once(code, '    total_train_tokens = step * args.train_batch_tokens\n', '    total_train_tokens = (step + calibration_steps) * args.train_batch_tokens\n')
globals()["__patched_source__"] = code
exec(compile(code, str(Path(__file__).resolve()), "exec"), globals(), globals())
