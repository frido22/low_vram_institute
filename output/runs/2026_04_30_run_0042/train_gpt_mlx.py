#!/usr/bin/env python3
from __future__ import annotations
from pathlib import Path

# Planner/launcher scanner markers kept literal:
# MAX_WALLCLOCK_SECONDS=600
# VAL_LOSS_EVERY=0
# final_int8_zlib_roundtrip_exact


def _find_base_script() -> Path:
    here = Path(__file__).resolve()
    for root in (here.parent, *here.parents):
        candidate = root / "state" / "best_script.py"
        if candidate.is_file():
            return candidate
    raise FileNotFoundError(f"Missing state/best_script.py relative to {here}")


def _replace_once(text: str, old: str, new: str) -> str:
    if old in text:
        return text.replace(old, new, 1)
    if new in text:
        return text
    raise RuntimeError(f"Missing patch target:\n{old}")


code = _find_base_script().read_text(encoding="utf-8")
code = _replace_once(code, 'code = Path(__file__).read_text(encoding="utf-8")\n', 'code = __patched_source__\n')
code = _replace_once(
    code,
    '    mlx_eager_eval: bool = bool(int(os.environ.get("MLX_EAGER_EVAL", "0")))\n',
    '    mlx_eager_eval: bool = bool(int(os.environ.get("MLX_EAGER_EVAL", "1")))\n',
)
code = _replace_once(
    code,
    '    if "MLX_EAGER_EVAL" not in os.environ:\n'
    '        args.mlx_eager_eval = not args.use_single_microbatch_path\n'
    '    elif args.use_single_microbatch_path and args.mlx_eager_eval:\n'
    '        log("WARNING: disabling MLX_EAGER_EVAL on single_microbatch_path for throughput")\n'
    '        args.mlx_eager_eval = False\n',
    '    if "MLX_EAGER_EVAL" not in os.environ:\n'
    '        args.mlx_eager_eval = True\n',
)
globals()["__patched_source__"] = code
exec(compile(code, str(Path(__file__).resolve()), "exec"), globals(), globals())
