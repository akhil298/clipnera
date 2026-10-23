#!/usr/bin/env bash
# Node 22 and Chrome's headless shell: what the graphics renderer (backend/beats/renderer/render.mjs) needs.
# Safe to run on every deploy: each tool is installed only when it is missing.
set -Eeuo pipefail
SUDO=""; [[ "$(id -u)" -ne 0 ]] && SUDO="sudo"
PACKAGE_MANAGER="dnf"; command -v dnf >/dev/null 2>&1 || PACKAGE_MANAGER="yum"
NODE_VERSION="22.11.0"
if ! command -v node >/dev/null 2>&1 || [[ "$(node -p 'process.versions.node.split(".")[0]')" -lt 22 ]]; then
    cd /tmp
    curl -fsSL "https://nodejs.org/dist/v${NODE_VERSION}/node-v${NODE_VERSION}-linux-x64.tar.xz" -o node.tar.xz
    ${SUDO} tar -xJf node.tar.xz -C /usr/local --strip-components=1
fi
echo "Node: $(node --version)"
if [[ ! -x /opt/chrome-headless-shell/chrome-headless-shell ]]; then
    ${SUDO} ${PACKAGE_MANAGER} install -y nss atk at-spi2-atk cups-libs libdrm libxkbcommon libXcomposite libXdamage \
        libXrandr mesa-libgbm pango alsa-lib unzip
    CHROME_ZIP_URL="$(curl -fsSL https://googlechromelabs.github.io/chrome-for-testing/last-known-good-versions-with-downloads.json \
        | python3 -c 'import json,sys; d=json.load(sys.stdin)["channels"]["Stable"]["downloads"]["chrome-headless-shell"]; print(next(x["url"] for x in d if x["platform"]=="linux64"))')"
    cd /tmp
    curl -fsSL "${CHROME_ZIP_URL}" -o chrome-headless-shell.zip
    ${SUDO} rm -rf /opt/chrome-headless-shell-linux64 /opt/chrome-headless-shell
    ${SUDO} unzip -q chrome-headless-shell.zip -d /opt
    ${SUDO} mv /opt/chrome-headless-shell-linux64 /opt/chrome-headless-shell
fi
echo "Chrome headless shell: /opt/chrome-headless-shell/chrome-headless-shell"
