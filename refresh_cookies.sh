#!/usr/bin/env bash
# Refresh the YouTube cookies on EC2 without deploying code: export them from
# the local browser (or take COOKIE_FILE as-is), copy them to the path the
# backend reads, check YouTube accepts them there, and restart the backend.
#
# Usage: bash refresh_cookies.sh [address]
#   address: IP or user@host; defaults to the last one update_ec2.sh used.
# Env overrides: EC2_KEY, COOKIE_BROWSER (default chrome), COOKIE_FILE, YOUTUBE_URL.
set -Eeuo pipefail

REPO_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PYTHON="${REPO_DIR}/backend/venv/bin/python"
EC2_KEY="${EC2_KEY:-${HOME}/Desktop/clipneras.pem}"
COOKIE_BROWSER="${COOKIE_BROWSER:-chrome}"
COOKIE_FILE="${COOKIE_FILE:-}"
YOUTUBE_URL="${YOUTUBE_URL:-https://www.youtube.com/watch?v=jNQXAC9IVRw}"

TARGET="${1:-$(cat "${HOME}/.config/clipnera/ec2_target" 2>/dev/null || true)}"
if [[ -z "${TARGET}" ]]; then
    echo "No EC2 address: pass one, e.g. bash refresh_cookies.sh 16.113.137.8" >&2
    exit 1
fi
[[ "${TARGET}" == *@* ]] || TARGET="ec2-user@${TARGET}"
REMOTE_COOKIE="/home/${TARGET%@*}/.clipnera/youtube_cookies.txt"
SSH_OPTS=(-i "${EC2_KEY}" -o IdentitiesOnly=yes -o ConnectTimeout=15 -o StrictHostKeyChecking=accept-new)

TMP_DIR="$(mktemp -d /tmp/clipnera-cookies.XXXXXX)"
trap 'rm -rf -- "${TMP_DIR}"' EXIT

if [[ -z "${COOKIE_FILE}" ]]; then
    echo "[1/3] Exporting cookies from ${COOKIE_BROWSER}..."
    # yt-dlp rejects an existing empty --cookies file, so give it a fresh path.
    COOKIE_FILE="${TMP_DIR}/cookies.txt"
    "${PYTHON}" -m yt_dlp --cookies-from-browser "${COOKIE_BROWSER}" --cookies "${COOKIE_FILE}" \
        --js-runtimes deno --remote-components ejs:github --skip-download --quiet "${YOUTUBE_URL}"
else
    echo "[1/3] Using ${COOKIE_FILE}..."
fi
if [[ ! -s "${COOKIE_FILE}" ]]; then
    echo "Cookie file is missing or empty: ${COOKIE_FILE}" >&2
    exit 1
fi

echo "[2/3] Copying cookies to ${TARGET}:${REMOTE_COOKIE}..."
ssh "${SSH_OPTS[@]}" "${TARGET}" "install -d -m 700 '$(dirname "${REMOTE_COOKIE}")'"
scp -q "${SSH_OPTS[@]}" "${COOKIE_FILE}" "${TARGET}:${REMOTE_COOKIE}"

echo "[3/3] Checking YouTube accepts them on EC2 and restarting the backend..."
ssh -T "${SSH_OPTS[@]}" "${TARGET}" bash -s -- "${REMOTE_COOKIE}" "${YOUTUBE_URL}" <<'REMOTE'
set -Eeuo pipefail
COOKIE="$1"; URL="$2"
BACKEND_DIR="${HOME}/clipnera_new/backend"
export PATH="${HOME}/.deno/bin:${PATH}"
chmod 600 "${COOKIE}"
# The backend falls back to this stale in-repo copy; remove it so it never masks the real one.
rm -f "${BACKEND_DIR}/youtube_cookies.txt"
echo "      YouTube title: $("${BACKEND_DIR}/venv/bin/python" -m yt_dlp --cookies "${COOKIE}" \
    --js-runtimes deno --remote-components ejs:github --skip-download --quiet --print '%(title)s' "${URL}")"
sudo systemctl restart clipnera-backend
echo "      Backend restarted."
REMOTE
