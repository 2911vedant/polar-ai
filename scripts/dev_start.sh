#!/bin/bash
# Start POLAR-AI backend in local dev mode (no Docker needed)
# Prerequisites: .venv exists, Python 3.11+, SQLite (no Postgres needed for demo mode)
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT="$SCRIPT_DIR/.."
BACKEND="$ROOT/backend"
VENV="$ROOT/.venv"

echo "=== POLAR-AI Dev Startup ==="

if [ ! -d "$VENV" ]; then
    echo "Creating virtual environment..."
    python3 -m venv "$VENV"
    "$VENV/bin/pip" install -q --upgrade pip
    "$VENV/bin/pip" install -q -r "$BACKEND/requirements.txt"
fi

cd "$BACKEND"

# Generate demo data + train models if needed
if [ ! -f "$ROOT/data/demo/DEMO_METADATA.json" ] && [ ! -f "$BACKEND/data/demo/DEMO_METADATA.json" ]; then
    echo "Generating demo data..."
    "$VENV/bin/python" -m data_pipeline.run_pipeline --demo-only
fi

if [ ! -f "$ROOT/models/rf_24h.pkl" ] && [ ! -f "$BACKEND/models/rf_24h.pkl" ]; then
    echo "Training sea ice models..."
    "$VENV/bin/python" -m app.ml.train_sea_ice || echo "Model training skipped"
fi

echo "Starting backend on http://localhost:8000 ..."
echo "API docs: http://localhost:8000/api/docs"
echo ""
DATABASE_URL="sqlite:///./dev.db" \
DATA_MODE=demo \
DEMO_RANDOM_SEED=42 \
SECRET_KEY=dev-secret-key \
DEBUG=true \
CORS_ORIGINS="http://localhost:3000,http://localhost:5173" \
"$VENV/bin/uvicorn" app.main:app --host 0.0.0.0 --port 8000 --reload
