#!/usr/bin/env bash
# Creates .venv next to this script and installs the dependencies of busytag.py.
set -euo pipefail

cd "$(dirname "$0")"

python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
# Pillow >= 10.1 is required for ImageFont.load_default(size=...)
.venv/bin/python -m pip install pyserial "pillow>=10.1"

echo "Done. Activate with: source .venv/bin/activate"
