#!/bin/bash
set -e

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "Project root: $ROOT_DIR"

echo "Activating virtual environment..."
source "$ROOT_DIR/apps/api/.venv/bin/activate"

echo "Starting API..."
cd "$ROOT_DIR/apps/api"

uvicorn app.main:app --reload --host 0.0.0.0 --port 8000