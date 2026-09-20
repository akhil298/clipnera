#!/usr/bin/env bash
set -Eeuo pipefail

echo "=========================================="
echo " ClipNera Backend - EC2 Setup"
echo "=========================================="

BACKEND_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd -- "${BACKEND_DIR}/.." && pwd)"
PYTHON_VERSION="${PYTHON_VERSION:-3.13.15}"
VENV_DIR="${BACKEND_DIR}/venv"

cd "${BACKEND_DIR}"

if [[ "$(id -u)" -eq 0 ]]; then
    SUDO=""
else
    SUDO="sudo"
fi

echo ""
echo "[1/10] Updating system..."
if command -v dnf >/dev/null 2>&1; then
    ${SUDO} dnf update -y
    PACKAGE_MANAGER="dnf"
elif command -v yum >/dev/null 2>&1; then
    ${SUDO} yum update -y
    PACKAGE_MANAGER="yum"
else
    echo "No dnf or yum package manager found." >&2
    exit 1
fi

echo ""
echo "[2/10] Installing system dependencies..."
${SUDO} "${PACKAGE_MANAGER}" install -y \
    git curl wget tar xz gcc gcc-c++ make \
    openssl-devel libffi-devel zlib-devel bzip2-devel \
    readline-devel sqlite-devel xz-devel tk-devel \
    gdbm-devel libuuid-devel

echo ""
echo "[3/10] Installing Python ${PYTHON_VERSION}..."
if ! command -v python3.13 >/dev/null 2>&1; then
    cd /tmp
    PYTHON_ARCHIVE="Python-${PYTHON_VERSION}.tgz"
    PYTHON_SOURCE_DIR="Python-${PYTHON_VERSION}"

    if [[ ! -d "${PYTHON_SOURCE_DIR}" ]]; then
        [[ -f "${PYTHON_ARCHIVE}" ]] || wget -q "https://www.python.org/ftp/python/${PYTHON_VERSION}/${PYTHON_ARCHIVE}"
        tar -xzf "${PYTHON_ARCHIVE}"
    fi

    cd "${PYTHON_SOURCE_DIR}"
    if [[ ! -x /usr/local/bin/python3.13 ]]; then
        ./configure --prefix=/usr/local --enable-optimizations
        make -j"$(nproc)"
        ${SUDO} make altinstall
    fi
fi

python3.13 --version

echo ""
echo "[4/10] Creating virtual environment..."
cd "${BACKEND_DIR}"
if [[ ! -x "${VENV_DIR}/bin/python" ]]; then
    python3.13 -m venv "${VENV_DIR}"
fi
source "${VENV_DIR}/bin/activate"
python --version
pip install --upgrade pip setuptools wheel

echo ""
echo "[5/10] Installing CPU-only PyTorch..."
pip install torch==2.8.0 --index-url https://download.pytorch.org/whl/cpu

echo ""
echo "[6/10] Installing application requirements..."
grep -v '^whisperx==' requirements.txt > /tmp/clipnera-requirements.txt
pip install -r /tmp/clipnera-requirements.txt

echo ""
echo "[7/10] Installing WhisperX without replacing CPU PyTorch..."
pip install --no-deps whisperx==3.7.4

echo ""
echo "[8/10] Installing FFmpeg..."
if ! command -v ffmpeg >/dev/null 2>&1; then
    cd /tmp
    FF_VERSION="7.0.2"
    FF_DIR="ffmpeg-${FF_VERSION}-amd64-static"
    FF_ARCHIVE="ffmpeg-release-amd64-static.tar.xz"

    if [[ ! -x "/usr/local/bin/ffmpeg" ]]; then
        [[ -f "${FF_ARCHIVE}" ]] || curl -L "https://johnvansickle.com/ffmpeg/releases/${FF_ARCHIVE}" -o "${FF_ARCHIVE}"
        [[ -d "${FF_DIR}" ]] || tar -xf "${FF_ARCHIVE}"
        ${SUDO} cp "${FF_DIR}/ffmpeg" "${FF_DIR}/ffprobe" /usr/local/bin/
        ${SUDO} chmod +x /usr/local/bin/ffmpeg /usr/local/bin/ffprobe
    fi
fi

echo "FFmpeg:"
ffmpeg -version | head -1
echo "FFprobe:"
ffprobe -version | head -1

echo ""
echo "[9/10] Installing Deno for yt-dlp..."
if ! command -v deno >/dev/null 2>&1 && [[ ! -x "${HOME}/.deno/bin/deno" ]]; then
    curl -fsSL https://deno.land/install.sh | sh
fi
export PATH="${HOME}/.deno/bin:${PATH}"
if ! command -v deno >/dev/null 2>&1; then
    echo "Deno installation failed or is not on PATH." >&2
    exit 1
fi
echo "Deno: $(command -v deno)"
deno --version

echo ""
echo "[10/10] Verifying Python environment..."
cd "${BACKEND_DIR}"
source "${VENV_DIR}/bin/activate"
python - <<'PY'
import sys
import torch
import asyncpg
import fastapi
import pydantic_settings
import yt_dlp

print("Python:", sys.version)
print("PyTorch:", torch.__version__)
print("CUDA available:", torch.cuda.is_available())
print("Backend dependencies: OK")
PY

PYTHONPATH="${BACKEND_DIR}" python -c "import main; print('Backend import OK')"

echo ""
echo "=========================================="
echo " SETUP COMPLETE"
echo "=========================================="
echo "Start the backend with:"
echo "  cd ${REPO_DIR}/backend"
echo "  bash start_backend.sh"