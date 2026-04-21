#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import os
from pathlib import Path

# The imported base script still enforces MAX_WALLCLOCK_SECONDS and prints
# final_int8_zlib_roundtrip_exact.
ROOT = Path(__file__).resolve().parents[2]
BASE_SCRIPT = ROOT / "state" / "best_script.py"

if not BASE_SCRIPT.is_file():
    raise FileNotFoundError(f"Missing current best script: {BASE_SCRIPT}")

os.environ.setdefault("INT8_PROJ_CLIP_PERCENTILE", "99.99")

spec = importlib.util.spec_from_file_location("best_script", BASE_SCRIPT)
if spec is None or spec.loader is None:
    raise ImportError(f"Unable to load best script from {BASE_SCRIPT}")

best_script = importlib.util.module_from_spec(spec)
spec.loader.exec_module(best_script)

best_script.INT8_PROJ_CLIP_PERCENTILE = float(os.environ["INT8_PROJ_CLIP_PERCENTILE"])
best_script.INT8_PROJ_CLIP_Q = best_script.INT8_PROJ_CLIP_PERCENTILE / 100.0

if __name__ == "__main__":
    best_script.main()
