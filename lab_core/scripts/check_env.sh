#!/bin/bash
set -euo pipefail

ENV_FILE="/Users/frido_mac/.config/low-vram-lab/env.sh"

if [ ! -f "$ENV_FILE" ]; then
  echo "missing: $ENV_FILE"
  exit 1
fi

source "$ENV_FILE"

if [ -z "${GITHUB_TOKEN:-}" ]; then
  echo "GITHUB_TOKEN is unset"
  exit 1
fi

echo "GITHUB_TOKEN is present"
