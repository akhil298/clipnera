#!/usr/bin/env bash
set -Eeuo pipefail

BACKEND_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd -- "${BACKEND_DIR}/.." && pwd)"

cd "${REPO_DIR}"
echo "Pulling latest backend code..."
git pull --ff-only

cd "${BACKEND_DIR}"

if [[ ! -x "${BACKEND_DIR}/venv/bin/python" ]]; then
  echo "Error: Python virtual environment not found at ${BACKEND_DIR}/venv" >&2
  exit 1
fi

export PATH="${HOME}/.deno/bin:${PATH}"
export PYTHONPATH="${BACKEND_DIR}"

if ! command -v deno >/dev/null 2>&1; then
  echo "Warning: deno was not found on PATH; yt-dlp JavaScript solving may fail." >&2
else
  echo "Using Deno: $(command -v deno)"
fi

echo "Starting backend on ${HOST:-0.0.0.0}:${PORT:-8000}..."
exec "${BACKEND_DIR}/venv/bin/python" -m uvicorn main:app \
  --host "${HOST:-0.0.0.0}" \
  --port "${PORT:-8000}"
