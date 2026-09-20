#!/usr/bin/env bash
set -Eeuo pipefail

REPO_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="${REPO_DIR}/backend"
COOKIE_FILE="${COOKIE_FILE:-}"
COOKIE_FILE_IS_TEMP=0
COOKIE_BROWSER="${COOKIE_BROWSER:-chrome}"
YOUTUBE_URL="${YOUTUBE_URL:-https://www.youtube.com/watch?v=eaHfex71yO0}"
EC2_USER="${EC2_USER:-ec2-user}"
EC2_HOST="${EC2_HOST:-16.113.137.8}"
EC2_KEY="${EC2_KEY:-${HOME}/Desktop/clipneras.pem}"
REMOTE_ROOT="${REMOTE_ROOT:-/home/ec2-user/clipnera_new}"
REMOTE_COOKIE="${REMOTE_ROOT}/backend/youtube_cookies.txt"

cleanup() {
    if [[ "${COOKIE_FILE_IS_TEMP}" -eq 1 ]]; then
        rm -f -- "${COOKIE_FILE}"
    fi
}
trap cleanup EXIT

if [[ -z "${COOKIE_FILE}" ]]; then
    COOKIE_FILE="$(mktemp /tmp/clipnera-youtube-cookies.XXXXXX)"
    COOKIE_FILE_IS_TEMP=1
fi

if [[ ! -x "${BACKEND_DIR}/venv/bin/python" ]]; then
    echo "Missing local backend/venv. Create it before running this script." >&2
    exit 1
fi
if [[ ! -f "${EC2_KEY}" ]]; then
    echo "EC2 key not found: ${EC2_KEY}" >&2
    exit 1
fi
if ! command -v ssh >/dev/null 2>&1 || ! command -v scp >/dev/null 2>&1; then
    echo "ssh and scp are required." >&2
    exit 1
fi
if ! command -v deno >/dev/null 2>&1; then
    echo "Deno is required locally for the YouTube cookie export." >&2
    exit 1
fi

chmod 400 "${EC2_KEY}"

echo "[1/4] Exporting fresh YouTube cookies from ${COOKIE_BROWSER}..."
"${BACKEND_DIR}/venv/bin/python" -m yt_dlp \
    --cookies-from-browser "${COOKIE_BROWSER}" \
    --cookies "${COOKIE_FILE}" \
    --js-runtimes deno \
    --remote-components ejs:github \
    --skip-download \
    --print '%(title)s' \
    "${YOUTUBE_URL}"

if [[ ! -s "${COOKIE_FILE}" ]]; then
    echo "Cookie export is empty: ${COOKIE_FILE}" >&2
    exit 1
fi

echo "[2/4] Copying cookies to ${EC2_USER}@${EC2_HOST}..."
scp -q -i "${EC2_KEY}" -o IdentitiesOnly=yes \
    "${COOKIE_FILE}" \
    "${EC2_USER}@${EC2_HOST}:${REMOTE_COOKIE}"

echo "[3/4] Preparing EC2 and validating YouTube access..."
ssh -T -i "${EC2_KEY}" -o IdentitiesOnly=yes \
    "${EC2_USER}@${EC2_HOST}" bash -s -- \
    "${REMOTE_ROOT}" "${REMOTE_COOKIE}" "${YOUTUBE_URL}" <<'REMOTE_SCRIPT'
set -Eeuo pipefail

REMOTE_ROOT="$1"
REMOTE_COOKIE="$2"
YOUTUBE_URL="$3"
BACKEND_DIR="${REMOTE_ROOT}/backend"
VENV_DIR="${BACKEND_DIR}/venv"

cd "${REMOTE_ROOT}"
git pull --ff-only
cd "${BACKEND_DIR}"

if [[ ! -x "${VENV_DIR}/bin/python" ]] || ! "${VENV_DIR}/bin/python" -c 'import yt_dlp' >/dev/null 2>&1; then
    bash setup_ec2.sh
fi

if [[ ! -x "${HOME}/.deno/bin/deno" ]] && ! command -v deno >/dev/null 2>&1; then
    curl -fsSL https://deno.land/install.sh | sh
fi
export PATH="${HOME}/.deno/bin:${PATH}"

chmod 600 "${REMOTE_COOKIE}"
touch .env
if grep -q '^YOUTUBE_COOKIES_PATH=' .env; then
    sed -i "s|^YOUTUBE_COOKIES_PATH=.*|YOUTUBE_COOKIES_PATH=${REMOTE_COOKIE}|" .env
else
    printf '\nYOUTUBE_COOKIES_PATH=%s\n' "${REMOTE_COOKIE}" >> .env
fi

"${VENV_DIR}/bin/python" -m yt_dlp \
    --cookies "${REMOTE_COOKIE}" \
    --js-runtimes deno \
    --remote-components ejs:github \
    --print '%(title)s' \
    "${YOUTUBE_URL}"

if [[ -f .backend.pid ]]; then
    BACKEND_PID="$(cat .backend.pid)"
    if kill -0 "${BACKEND_PID}" 2>/dev/null; then
        kill "${BACKEND_PID}"
        for _ in {1..20}; do
            kill -0 "${BACKEND_PID}" 2>/dev/null || break
            sleep 1
        done
    fi
fi

while read -r BACKEND_PID; do
    [[ -n "${BACKEND_PID}" ]] || continue
    kill "${BACKEND_PID}" 2>/dev/null || true
done < <(pgrep -f "${VENV_DIR}/bin/python -m uvicorn main:app" || true)

export PATH="${HOME}/.deno/bin:${PATH}"
nohup bash start_backend.sh > backend.log 2>&1 &
echo $! > .backend.pid
sleep 3
if ! kill -0 "$(cat .backend.pid)" 2>/dev/null; then
    echo "Backend failed to start. Check ${BACKEND_DIR}/backend.log" >&2
    exit 1
fi
REMOTE_SCRIPT

echo "[4/4] EC2 update complete. Backend restarted on ${EC2_HOST}:8000."
