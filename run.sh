#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# BotanicalTox — launcher
#
# Production default: starts GUNICORN, which handles long training requests.
#   ./run.sh                      → gunicorn on 0.0.0.0:5001 (2 workers, 300s timeout)
#   ./run.sh dev                  → Flask dev server (hot reload, single user)
#
# Overrides:
#   PORT=8080 ./run.sh            → change port
#   WEB_CONCURRENCY=4 ./run.sh    → change worker count
#   GUNICORN_TIMEOUT=600 ./run.sh → change request timeout (default 300s)
# ─────────────────────────────────────────────────────────────────────────────
set -e
cd "$(dirname "$0")"

PY=python3
if [ -x venv/bin/python ]; then
    PY=venv/bin/python
    echo "Using project virtual environment: venv/"
fi

PORT="${PORT:-5001}"
WORKERS="${WEB_CONCURRENCY:-2}"
TIMEOUT="${GUNICORN_TIMEOUT:-300}"

if [ "$1" = "dev" ]; then
    echo "Starting BotanicalTox (dev server) on http://localhost:$PORT ..."
    exec "$PY" app.py
fi

echo "Starting BotanicalTox (gunicorn) on 0.0.0.0:$PORT (workers=$WORKERS, timeout=${TIMEOUT}s) ..."
exec "$PY" -m gunicorn \
    --workers "$WORKERS" \
    --timeout "$TIMEOUT" \
    --graceful-timeout 30 \
    --bind "0.0.0.0:$PORT" \
    app:app
