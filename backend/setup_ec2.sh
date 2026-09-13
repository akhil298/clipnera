#!/usr/bin/env bash
set -Eeuo pipefail

BACKEND_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd -- "${BACKEND_DIR}/.." && pwd)"
PYTHON_BIN="${PYTHON_BIN:-python3}"

cd "${BACKEND_DIR}"

if [[ "$(id -u)" -eq 0 ]]; then
  SUDO=""
else
  SUDO="sudo"
fi

echo "==> Installing system prerequisites"
if command -v dnf >/dev/null 2>&1; then
  ${SUDO} dnf install -y python3 python3-pip python3-devel gcc gcc-c++ make curl
elif command -v yum >/dev/null 2>&1; then
  ${SUDO} yum install -y python3 python3-pip python3-devel gcc gcc-c++ make curl
else
  echo "Unsupported package manager. Install Python 3, pip, and build tools manually." >&2
  exit 1
fi

if ! command -v ffmpeg >/dev/null 2>&1; then
  echo "WARNING: FFmpeg is not installed or is not on PATH." >&2
else
  echo "Using FFmpeg: $(command -v ffmpeg)"
  ffmpeg -hide_banner -version | sed -n '1p'
fi

echo "==> Creating Python virtual environment"
if [[ ! -x "${BACKEND_DIR}/.venv/bin/python" ]]; then
  "${PYTHON_BIN}" -m venv "${BACKEND_DIR}/.venv"
fi

echo "==> Installing Python dependencies"
"${BACKEND_DIR}/.venv/bin/python" -m pip install --upgrade pip setuptools wheel
"${BACKEND_DIR}/.venv/bin/python" -m pip install -r "${BACKEND_DIR}/requirements.txt"

echo "==> Installing Deno for yt-dlp JavaScript solving"
if ! command -v deno >/dev/null 2>&1 && [[ ! -x "${HOME}/.deno/bin/deno" ]]; then
  curl -fsSL https://deno.land/install.sh | sh
fi

export PATH="${HOME}/.deno/bin:${PATH}"
if command -v deno >/dev/null 2>&1; then
  echo "Using Deno: $(command -v deno)"
  deno --version
else
  echo "WARNING: Deno installation was not found on PATH." >&2
fi

echo "==> Checking FFmpeg encoders"
if command -v ffmpeg >/dev/null 2>&1; then
  ffmpeg -hide_banner -encoders 2>&1 | grep -E 'libx264|libopenh264|h264_nvenc|mpeg4' || \
    echo "WARNING: No supported video encoder was listed."
fi

echo "==> Checking backend imports"
PYTHONPATH="${BACKEND_DIR}" "${BACKEND_DIR}/.venv/bin/python" -c \
  "import fastapi, pydantic_settings, yt_dlp; print('Backend dependencies OK')"

echo
echo "Setup complete. Start the backend with:"
echo "  cd ${REPO_DIR}/backend && bash start_backend.sh"