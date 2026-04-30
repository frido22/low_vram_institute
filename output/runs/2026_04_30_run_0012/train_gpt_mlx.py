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
    candidate = Path.cwd() / "state" / "best_script.py"
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
    'PROJ_EMA_DECAY = float(os.environ.get("PROJ_EMA_DECAY", 0.94))',
    'PROJ_EMA_DECAY = float(os.environ.get("PROJ_EMA_DECAY", 0.68))',
)
code = _replace_once(
    code,
    '    log("tail_ema:decay:{:.2f} tracked_float_kept:all tracked_proj_suffixes:all".format(PROJ_EMA_DECAY))\n',
    '    log("tail_ema:decay:{:.2f} tracked_float_kept:all tracked_proj_suffixes:all update:roundtrip_anchored".format(PROJ_EMA_DECAY))\n',
)
code = _replace_once(
    code,
    '        if last_quant_aware_step is not None:\n            flat_params = dict(tree_flatten(model.parameters()))\n            if tracked_ema is None:\n',
    '        if did_quant_aware_roundtrip:\n            flat_params = dict(tree_flatten(model.parameters()))\n            if tracked_ema is None:\n',
)
code = _replace_once(
    code,
    '        log(f"quant_aware_roundtrip:step:{step} final_pre_save")\n    if tracked_ema:\n',
    '        log(f"quant_aware_roundtrip:step:{step} final_pre_save")\n        if tracked_ema:\n            flat_params = dict(tree_flatten(model.parameters()))\n            for name in tracked_ema:\n                tracked_ema[name] = tracked_ema[name] + (flat_params[name] - tracked_ema[name]) * tracked_ema_keep\n    if tracked_ema:\n',
)
globals()["__patched_source__"] = code
exec(compile(code, str(Path(__file__).resolve()), "exec"), globals(), globals())
