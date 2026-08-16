#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# BotanicalTox — launcher
# Uses the project virtual environment (venv/) when available, otherwise
# falls back to the system python3.
#
# Usage:
#     ./run.sh            # start the server on http://localhost:5001
# ─────────────────────────────────────────────────────────────────────────────
set -e
cd "$(dirname "$0")"

PY=python3
if [ -x venv/bin/python ]; then
    PY=venv/bin/python
    echo "Using project virtual environment: venv/"
fi

echo "Starting BotanicalTox ..."
exec "$PY" app.py
