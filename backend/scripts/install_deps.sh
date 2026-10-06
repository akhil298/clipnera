#!/usr/bin/env bash
# Install whatever requirements.txt lists that the venv does not have yet.
#
# Only missing or out-of-range packages are installed, one at a time and
# without pip's download cache, so an update costs the disk space of what
# changed. torch/torchaudio come from the CPU-only index and are held there by
# a constraints file: nothing installed later can swap in the multi-GB CUDA
# build. WhisperX is installed with --no-deps for the same reason; its own
# requirements are listed in requirements.txt.
#
# Usage: bash scripts/install_deps.sh   (from backend/, venv at backend/venv)
set -Eeuo pipefail

BACKEND_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
PY="${BACKEND_DIR}/venv/bin/python"
TORCH_VERSION="2.8.0"
TORCH_INDEX="https://download.pytorch.org/whl/cpu"
NO_DEPS="whisperx"

PIP=("${PY}" -m pip install --no-cache-dir --disable-pip-version-check)
CONSTRAINTS="$(mktemp)"
trap 'rm -f "${CONSTRAINTS}"' EXIT
printf 'torch==%s\ntorchaudio==%s\n' "${TORCH_VERSION}" "${TORCH_VERSION}" > "${CONSTRAINTS}"

echo "Upgrading pip..."
"${PIP[@]}" --quiet --upgrade pip setuptools wheel

# Prints each requirement the venv does not satisfy, one per line.
missing() {
    "${PY}" - "$@" <<'PY'
import sys
from importlib.metadata import PackageNotFoundError, version
from pip._vendor.packaging.requirements import Requirement

for line in sys.argv[1:]:
    req = Requirement(line)
    if req.marker and not req.marker.evaluate():
        continue
    try:
        installed = version(req.name)
    except PackageNotFoundError:
        print(line)
        continue
    if req.specifier and not req.specifier.contains(installed, prereleases=True):
        print(line)
PY
}

mapfile -t TORCH_MISSING < <(missing "torch==${TORCH_VERSION}" "torchaudio==${TORCH_VERSION}")
if (( ${#TORCH_MISSING[@]} )); then
    echo "Installing CPU-only ${TORCH_MISSING[*]}..."
    "${PIP[@]}" "${TORCH_MISSING[@]}" --index-url "${TORCH_INDEX}"
fi

mapfile -t REQUIREMENTS < <(sed -e 's/[[:space:]]*#.*//' -e '/^[[:space:]]*$/d' "${BACKEND_DIR}/requirements.txt")
mapfile -t TO_INSTALL < <(missing "${REQUIREMENTS[@]}")
if (( ! ${#TO_INSTALL[@]} )); then
    echo "All requirements already installed."
fi
for req in "${TO_INSTALL[@]}"; do
    echo "Installing ${req}..."
    if [[ "${req}" == ${NO_DEPS}* ]]; then
        "${PIP[@]}" --no-deps "${req}"
    else
        "${PIP[@]}" -c "${CONSTRAINTS}" "${req}"
    fi
done

# Reported, not fatal: whisperx's skipped CUDA extras always show up here.
"${PY}" -m pip check 2>/dev/null | grep -v '^whisperx ' || true
