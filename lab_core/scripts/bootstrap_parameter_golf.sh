#!/bin/bash
set -euo pipefail

ROOT="/Users/frido_mac/Projects/low_vram_institute"
WORKSPACE="$ROOT/third_party/parameter-golf"
VENV="$WORKSPACE/.venv_pg"

if [ ! -d "$WORKSPACE" ]; then
  git clone https://github.com/openai/parameter-golf.git "$WORKSPACE"
fi

if [ ! -d "$VENV" ]; then
  python3 -m venv "$VENV"
fi

"$VENV/bin/python3" -m pip install --upgrade pip
"$VENV/bin/pip" install mlx numpy sentencepiece huggingface-hub datasets tqdm
"$VENV/bin/python3" data/cached_challenge_fineweb.py --variant sp1024 --train-shards 1

echo "Parameter Golf bootstrap complete"
