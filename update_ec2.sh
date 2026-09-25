#!/usr/bin/env bash
# Pull the latest code on EC2 and restart the backend service. YouTube cookies
# are exported from this machine's browser and copied over only when the ones
# already on EC2 are missing, near expiry or rejected by YouTube.
#
# Usage: bash update_ec2.sh [address]
#   address: an IP/hostname, user@host, or a pasted "ssh -i key user@host"
#   command. Asked for when omitted; Enter reuses the last address.
# Env overrides: EC2_KEY, COOKIE_BROWSER, COOKIE_FILE (push this cookies.txt
# as-is instead of exporting from the browser), FORCE_COOKIES=1 (replace the
# cookies on EC2 even if they still work), COOKIE_MIN_DAYS (default 2),
# YOUTUBE_URL.
set -Eeuo pipefail

REPO_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="${REPO_DIR}/backend"
COOKIE_FILE="${COOKIE_FILE:-}"
COOKIE_TMP_DIR=""
COOKIE_BROWSER="${COOKIE_BROWSER:-chrome}"
FORCE_COOKIES="${FORCE_COOKIES:-0}"
# Refresh the server's cookies once their sign-in expires within this many days.
COOKIE_MIN_DAYS="${COOKIE_MIN_DAYS:-2}"
YOUTUBE_URL="${YOUTUBE_URL:-https://www.youtube.com/watch?v=eaHfex71yO0}"
EC2_KEY="${EC2_KEY:-${HOME}/Desktop/clipneras.pem}"
LAST_TARGET_FILE="${HOME}/.config/clipnera/ec2_target"

cleanup() {
    if [[ -n "${COOKIE_TMP_DIR}" ]]; then
        rm -rf -- "${COOKIE_TMP_DIR}"
    fi
}
trap cleanup EXIT

# --- Where to deploy -------------------------------------------------------
LAST_TARGET="$(cat "${LAST_TARGET_FILE}" 2>/dev/null || true)"
TARGET="${1:-}"
if [[ -z "${TARGET}" ]]; then
    read -r -p "EC2 address (IP, user@host or ssh command)${LAST_TARGET:+ [${LAST_TARGET}]}: " TARGET
    TARGET="${TARGET:-${LAST_TARGET}}"
fi
# A pasted ssh command ends with user@host; keep only that last word.
TARGET="$(echo "${TARGET}" | xargs)"
TARGET="${TARGET##* }"
TARGET="${TARGET%\~}"  # stray terminal bracketed-paste marker
if [[ -z "${TARGET}" ]]; then
    echo "No EC2 address given." >&2
    exit 1
fi
if [[ "${TARGET}" == *@* ]]; then
    EC2_USER="${TARGET%@*}"
    EC2_HOST="${TARGET#*@}"
else
    EC2_USER="ec2-user"
    EC2_HOST="${TARGET}"
fi
REMOTE_ROOT="/home/${EC2_USER}/clipnera_new"
# Kept outside the repo so git pull never touches it and it is never committed.
REMOTE_COOKIE="/home/${EC2_USER}/.clipnera/youtube_cookies.txt"
SSH_OPTS=(-i "${EC2_KEY}" -o IdentitiesOnly=yes -o ConnectTimeout=15 -o StrictHostKeyChecking=accept-new)

# --- Local checks ----------------------------------------------------------
if [[ ! -f "${EC2_KEY}" ]]; then
    echo "EC2 key not found: ${EC2_KEY}" >&2
    exit 1
fi
chmod 400 "${EC2_KEY}"

echo "[0/4] Checking SSH access to ${EC2_USER}@${EC2_HOST}..."
if ! ssh "${SSH_OPTS[@]}" "${EC2_USER}@${EC2_HOST}" true; then
    echo "Cannot SSH to ${EC2_USER}@${EC2_HOST}. Is the instance running, the address current, and port 22 open to your IP?" >&2
    exit 1
fi
mkdir -p "$(dirname "${LAST_TARGET_FILE}")"
echo "${EC2_USER}@${EC2_HOST}" > "${LAST_TARGET_FILE}"

if [[ -n "$(git -C "${REPO_DIR}" log '@{u}..' --oneline 2>/dev/null)" ]]; then
    echo "WARNING: you have unpushed commits; EC2 pulls from GitHub and will not get them." >&2
fi

# --- Cookies ---------------------------------------------------------------
# The backend writes YouTube's rotated cookies back to REMOTE_COOKIE after each
# use, so the copy on EC2 stays fresh by itself. Overwriting it on every deploy
# replaced those good cookies with a browser export that goes stale as soon as
# the browser rotates its session. Only push when the server's copy is missing,
# close to expiry or refused by YouTube, or when asked to.
cookies_valid_on_ec2() {
    ssh -T "${SSH_OPTS[@]}" "${EC2_USER}@${EC2_HOST}" bash -s -- \
        "${REMOTE_ROOT}/backend/venv/bin/python" "${REMOTE_COOKIE}" "${YOUTUBE_URL}" "${COOKIE_MIN_DAYS}" <<'CHECK_SCRIPT'
set -uo pipefail
PYTHON="$1"; COOKIE="$2"; URL="$3"; MIN_DAYS="$4"
export PATH="${HOME}/.deno/bin:${PATH}"

[[ -s "${COOKIE}" ]] || { echo "      no cookies on EC2 yet"; exit 1; }
[[ -x "${PYTHON}" ]] && command -v deno >/dev/null 2>&1 || { echo "      EC2 is not set up to check cookies"; exit 1; }

# Signed-in session cookies; the file is useless once these lapse.
"${PYTHON}" - "${COOKIE}" "${MIN_DAYS}" <<'PY' || exit 1
import sys, time
path, min_days = sys.argv[1], float(sys.argv[2])
expiries = []
for line in open(path, encoding="utf-8", errors="ignore"):
    fields = line.removeprefix("#HttpOnly_").rstrip("\n").split("\t")
    if len(fields) == 7 and "youtube.com" in fields[0] and fields[5] in ("LOGIN_INFO", "__Secure-3PSID"):
        expiries.append(int(fields[4] or 0))
if not expiries:
    print("      cookies on EC2 are not signed in")
    sys.exit(1)
days_left = (min(expiries) - time.time()) / 86400
if days_left < min_days:
    print(f"      cookies on EC2 expire in {days_left:.1f} days")
    sys.exit(1)
print(f"      cookies on EC2 are valid for {days_left:.0f} more days")
PY

"${PYTHON}" -m yt_dlp --cookies "${COOKIE}" --js-runtimes deno --remote-components ejs:github \
    --skip-download --quiet --no-warnings --print '%(title)s' "${URL}" >/dev/null 2>&1 \
    || { echo "      YouTube refused the cookies on EC2"; exit 1; }
CHECK_SCRIPT
}

PUSH_COOKIES=1
if [[ -n "${COOKIE_FILE}" || "${FORCE_COOKIES}" == "1" ]]; then
    echo "[1/4] Refreshing YouTube cookies as requested..."
else
    echo "[1/4] Checking YouTube cookies on EC2..."
    if cookies_valid_on_ec2; then
        PUSH_COOKIES=0
        echo "      Keeping them (set FORCE_COOKIES=1 to replace them anyway)."
    else
        echo "      Exporting fresh cookies from ${COOKIE_BROWSER}..."
    fi
fi

if [[ "${PUSH_COOKIES}" == "0" ]]; then
    :
elif [[ -n "${COOKIE_FILE}" ]]; then
    echo "      Using cookies file ${COOKIE_FILE}."
    if [[ ! -s "${COOKIE_FILE}" ]]; then
        echo "Cookies file is missing or empty: ${COOKIE_FILE}" >&2
        exit 1
    fi
else
    if [[ ! -x "${BACKEND_DIR}/venv/bin/python" ]]; then
        echo "Missing local backend/venv. Create it before running this script." >&2
        exit 1
    fi
    if ! command -v deno >/dev/null 2>&1; then
        echo "Deno is required locally for the YouTube cookie export." >&2
        exit 1
    fi
    # yt-dlp loads an existing --cookies file before writing it and rejects an
    # empty one, so hand it a path that does not exist yet.
    COOKIE_TMP_DIR="$(mktemp -d /tmp/clipnera-youtube-cookies.XXXXXX)"
    COOKIE_FILE="${COOKIE_TMP_DIR}/cookies.txt"

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
fi

if [[ "${PUSH_COOKIES}" == "1" ]]; then
    echo "[2/4] Copying cookies to ${EC2_USER}@${EC2_HOST}:${REMOTE_COOKIE}..."
    ssh "${SSH_OPTS[@]}" "${EC2_USER}@${EC2_HOST}" "install -d -m 700 '$(dirname "${REMOTE_COOKIE}")'"
    scp -q "${SSH_OPTS[@]}" "${COOKIE_FILE}" "${EC2_USER}@${EC2_HOST}:${REMOTE_COOKIE}"
else
    echo "[2/4] Cookies on EC2 are still good; not copying."
fi

# --- Server update ---------------------------------------------------------
echo "[3/4] Updating code, validating YouTube access and restarting backend..."
ssh -T "${SSH_OPTS[@]}" "${EC2_USER}@${EC2_HOST}" bash -s -- \
    "${REMOTE_ROOT}" "${REMOTE_COOKIE}" "${YOUTUBE_URL}" <<'REMOTE_SCRIPT'
set -Eeuo pipefail

REMOTE_ROOT="$1"
REMOTE_COOKIE="$2"
YOUTUBE_URL="$3"
BACKEND_DIR="${REMOTE_ROOT}/backend"
VENV_DIR="${BACKEND_DIR}/venv"
SERVICE=clipnera-backend

cd "${REMOTE_ROOT}"
# Older runs wrote cookies into the tracked backend/youtube_cookies.txt; drop
# that local edit so the pull (which untracks the file) is not blocked by it.
git checkout -- backend/youtube_cookies.txt 2>/dev/null || true
# Any other code edited in place on the server would block the pull; stash it
# so nothing is lost.
if ! git diff --quiet || ! git diff --cached --quiet; then
    git stash push -m "update_ec2: server edits $(date -u +%FT%TZ)"
    echo "WARNING: server had local code edits; stashed them (see: git stash list)." >&2
fi
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
# Settings load from .env or .env.production depending on ENVIRONMENT, so
# point every env file present at the cookies, replacing any older path.
touch .env
for ENV_FILE in .env .env.production; do
    [[ -f "${ENV_FILE}" ]] || continue
    if grep -q '^YOUTUBE_COOKIES_PATH=' "${ENV_FILE}"; then
        sed -i "s|^YOUTUBE_COOKIES_PATH=.*|YOUTUBE_COOKIES_PATH=${REMOTE_COOKIE}|" "${ENV_FILE}"
    else
        printf '\nYOUTUBE_COOKIES_PATH=%s\n' "${REMOTE_COOKIE}" >> "${ENV_FILE}"
    fi
done

"${VENV_DIR}/bin/python" -m yt_dlp \
    --cookies "${REMOTE_COOKIE}" \
    --js-runtimes deno \
    --remote-components ejs:github \
    --skip-download \
    --print '%(title)s' \
    "${YOUTUBE_URL}"

# systemd keeps the backend up across SSH logouts and reboots.
sudo tee "/etc/systemd/system/${SERVICE}.service" >/dev/null <<UNIT
[Unit]
Description=Clipnera backend
After=network-online.target
Wants=network-online.target

[Service]
User=$(id -un)
WorkingDirectory=${BACKEND_DIR}
Environment=PATH=${HOME}/.deno/bin:/usr/local/bin:/usr/bin:/bin
Environment=PYTHONPATH=${BACKEND_DIR}
ExecStart=${VENV_DIR}/bin/python -m uvicorn main:app --host 0.0.0.0 --port 8000
Restart=on-failure
RestartSec=5
StandardOutput=append:${BACKEND_DIR}/backend.log
StandardError=append:${BACKEND_DIR}/backend.log

[Install]
WantedBy=multi-user.target
UNIT
sudo systemctl daemon-reload
sudo systemctl enable --quiet "${SERVICE}"
sudo systemctl stop "${SERVICE}" || true

# Backends started by hand (start_backend.sh / nohup) would hold port 8000.
pkill -f "uvicorn main:app" 2>/dev/null || true
rm -f .backend.pid
sleep 2

sudo systemctl start "${SERVICE}"

# The social publisher worker (python -m social.worker) runs beside the API. It
# refuses to start without a token key ring, so only run it once one is set.
PUBLISHER=clipnera-publisher
if grep -qsE '^SOCIAL_TOKEN_ENCRYPTION_KEYS=.+' .env .env.production; then
    sudo tee "/etc/systemd/system/${PUBLISHER}.service" >/dev/null <<UNIT
[Unit]
Description=Clipnera social publisher worker
After=network-online.target ${SERVICE}.service
Wants=network-online.target

[Service]
User=$(id -un)
WorkingDirectory=${BACKEND_DIR}
Environment=PYTHONPATH=${BACKEND_DIR}
ExecStart=${VENV_DIR}/bin/python -m social.worker
Restart=on-failure
RestartSec=30
StandardOutput=append:${BACKEND_DIR}/publisher.log
StandardError=append:${BACKEND_DIR}/publisher.log

[Install]
WantedBy=multi-user.target
UNIT
    sudo systemctl daemon-reload
    sudo systemctl enable --quiet "${PUBLISHER}"
    sudo systemctl restart "${PUBLISHER}"
else
    echo "Skipping ${PUBLISHER}: SOCIAL_TOKEN_ENCRYPTION_KEYS is not set." >&2
fi

for _ in {1..60}; do
    if curl -fsS http://127.0.0.1:8000/health >/dev/null 2>&1; then
        echo "Backend healthy: $(curl -fsS http://127.0.0.1:8000/health)"
        exit 0
    fi
    sleep 2
done
echo "Backend did not become healthy. Last log lines:" >&2
tail -40 backend.log >&2
exit 1
REMOTE_SCRIPT

echo "[4/4] EC2 update complete. Backend running on ${EC2_HOST}:8000."
echo "      Logs: ssh ${EC2_USER}@${EC2_HOST} 'tail -f ${REMOTE_ROOT}/backend/backend.log'"
