#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# CRABLOX — launcher
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
CONDA_PY="$HOME/miniforge3/envs/crablox/bin/python"
if [ -x "$CONDA_PY" ]; then
    PY="$CONDA_PY"
    echo "Using conda environment: crablox (RDKit $($PY -c 'import rdkit;print(rdkit.__version__)'))"
elif [ -x venv/bin/python ]; then
    PY=venv/bin/python
    echo "Using project virtual environment: venv/"
fi

PORT="${PORT:-5001}"
WORKERS="${WEB_CONCURRENCY:-2}"
TIMEOUT="${GUNICORN_TIMEOUT:-300}"
MAX_REQUESTS="${GUNICORN_MAX_REQUESTS:-2000}"
MAX_REQUESTS_JITTER="${GUNICORN_MAX_REQUESTS_JITTER:-200}"

if [ "$1" = "dev" ]; then
    echo "Starting CRABLOX (dev server) on http://localhost:$PORT ..."
    exec "$PY" app.py
fi

echo "Starting CRABLOX (gunicorn) on 0.0.0.0:$PORT (workers=$WORKERS, timeout=${TIMEOUT}s) ..."
export OMP_NUM_THREADS=1
export MKL_NUM_THREADS=1
export OPENBLAS_NUM_THREADS=1
export NUMEXPR_NUM_THREADS=1
exec "$PY" -m gunicorn \
    --workers "$WORKERS" \
    --timeout "$TIMEOUT" \
    --graceful-timeout 30 \
    --max-requests "$MAX_REQUESTS" \
    --max-requests-jitter "$MAX_REQUESTS_JITTER" \
    --bind "0.0.0.0:$PORT" \
    app:app
