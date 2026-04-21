#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import os
from pathlib import Path

# The imported base script still emits final_int8_zlib_roundtrip_exact and
# enforces MAX_WALLCLOCK_SECONDS.
ROOT = Path(__file__).resolve().parents[2]
BASE_SCRIPT = ROOT / "state" / "best_script.py"

if not BASE_SCRIPT.is_file():
    raise FileNotFoundError(f"Missing current best script: {BASE_SCRIPT}")

os.environ.setdefault("INT8_ROW_OFFSET_MIN_RATIO", "0.01")

spec = importlib.util.spec_from_file_location("best_script", BASE_SCRIPT)
if spec is None or spec.loader is None:
    raise ImportError(f"Unable to load best script from {BASE_SCRIPT}")

best_script = importlib.util.module_from_spec(spec)
spec.loader.exec_module(best_script)

best_script.INT8_ROW_OFFSET_MIN_RATIO = float(os.environ["INT8_ROW_OFFSET_MIN_RATIO"])

if __name__ == "__main__":
    best_script.main()
