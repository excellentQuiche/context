#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

if [ ! -d .venv ]; then
    echo "Virtual environment not found. Create .venv and install requirements first." >&2
    exit 1
fi

source .venv/bin/activate
exec python -m uvicorn app.main:app --reload
