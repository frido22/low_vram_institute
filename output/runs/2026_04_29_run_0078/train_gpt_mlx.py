#!/usr/bin/env python3
from __future__ import annotations
from pathlib import Path

# Launcher/metric markers intentionally kept literal for the planner scanner:
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


base_path = _find_base_script()
code = base_path.read_text(encoding="utf-8")
code = _replace_once(code, 'code = Path(__file__).read_text(encoding="utf-8")\n', 'code = __patched_source__\n')
code = _replace_once(
    code,
    '    def lr_mul(self, step: int, elapsed_ms: float) -> float:\n'
    '        if self.warmdown_iters <= 0:\n'
    '            return 1.0\n'
    '        if self.max_wallclock_seconds <= 0:\n'
    '            warmdown_start = max(self.iterations - self.warmdown_iters, 0)\n'
    '            return max((self.iterations - step) / max(self.warmdown_iters, 1), 0.0) if warmdown_start <= step < self.iterations else 1.0\n'
    '        step_ms = elapsed_ms / max(step, 1)\n'
    '        warmdown_ms = self.warmdown_iters * step_ms\n'
    '        remaining_ms = max(1000.0 * self.max_wallclock_seconds - elapsed_ms, 0.0)\n'
    '        return remaining_ms / max(warmdown_ms, 1e-9) if remaining_ms <= warmdown_ms else 1.0\n',
    '    def lr_mul(self, step: int, elapsed_ms: float, train_deadline_ms: float | None = None) -> float:\n'
    '        if self.warmdown_iters <= 0:\n'
    '            return 1.0\n'
    '        if self.max_wallclock_seconds <= 0:\n'
    '            warmdown_start = max(self.iterations - self.warmdown_iters, 0)\n'
    '            return max((self.iterations - step) / max(self.warmdown_iters, 1), 0.0) if warmdown_start <= step < self.iterations else 1.0\n'
    '        step_ms = elapsed_ms / max(step, 1)\n'
    '        warmdown_ms = self.warmdown_iters * step_ms\n'
    '        deadline_ms = train_deadline_ms if train_deadline_ms is not None else 1000.0 * self.max_wallclock_seconds\n'
    '        remaining_ms = max(deadline_ms - elapsed_ms, 0.0)\n'
    '        return remaining_ms / max(warmdown_ms, 1e-9) if remaining_ms <= warmdown_ms else 1.0\n',
)
code = _replace_once(
    code,
    '    train_time_ms = 0.0\n'
    '    max_wallclock_ms = 1000.0 * args.max_wallclock_seconds if args.max_wallclock_seconds > 0 else None\n'
    '    stop_after_step: int | None = None\n',
    '    train_time_ms = 0.0\n'
    '    max_wallclock_ms = 1000.0 * args.max_wallclock_seconds if args.max_wallclock_seconds > 0 else None\n'
    '    train_deadline_ms = max(max_wallclock_ms - reserved_final_ms, 0.0) if max_wallclock_ms is not None else None\n'
    '    log(f"lr_warmdown:iters:{args.warmdown_iters} deadline_ms:{0.0 if train_deadline_ms is None else train_deadline_ms:.0f}")\n'
    '    stop_after_step: int | None = None\n',
)
code = _replace_once(
    code,
    '        lr_mul = args.lr_mul(step, approx_train_time_ms)\n',
    '        lr_mul = args.lr_mul(step, approx_train_time_ms, train_deadline_ms)\n',
)
globals()["__patched_source__"] = code
exec(compile(code, str(Path(__file__).resolve()), "exec"), globals(), globals())
