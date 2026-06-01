#!/usr/bin/env bash
# Creates a virtual environment (if it does not already exist), installs the
# project dependencies into it, and runs the sample client.
set -euo pipefail

VENV_DIR="env"
MIN_PY_MAJOR=3
MIN_PY_MINOR=10

# Require Python 3.10+ (the pinned dependencies do not support older versions).
if ! python3 -c "import sys; sys.exit(0 if sys.version_info >= ($MIN_PY_MAJOR, $MIN_PY_MINOR) else 1)"; then
    echo "Error: Python ${MIN_PY_MAJOR}.${MIN_PY_MINOR}+ is required, but found $(python3 --version 2>&1)." >&2
    echo "Please install a newer Python and re-run ./start.sh" >&2
    exit 1
fi

if [ ! -d "$VENV_DIR" ]; then
    echo "Creating virtual environment in ./$VENV_DIR ..."
    python3 -m venv "$VENV_DIR"
else
    echo "Virtual environment ./$VENV_DIR already exists."
fi

# shellcheck disable=SC1091
source "$VENV_DIR/bin/activate"

echo "Installing dependencies from requirements.txt ..."
pip install --upgrade pip
pip install -r requirements.txt

echo "Running main.py ..."
python main.py
