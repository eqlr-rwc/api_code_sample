#!/usr/bin/env bash
# Creates a virtual environment (if it does not already exist), installs the
# project dependencies into it, and runs the sample client.
set -euo pipefail

VENV_DIR="env"

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
