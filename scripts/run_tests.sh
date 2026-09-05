#!/bin/bash
# Run POLAR-AI backend tests
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT="$SCRIPT_DIR/.."
BACKEND="$ROOT/backend"
VENV="$ROOT/.venv"

echo "=== POLAR-AI Backend Tests ==="

if [ ! -d "$VENV" ]; then
    echo "Creating virtual environment..."
    python3 -m venv "$VENV"
    "$VENV/bin/pip" install -q -r "$BACKEND/requirements.txt"
fi

cd "$BACKEND"
"$VENV/bin/python" -m pytest tests/ -v "$@"
