#!/usr/bin/env bash
# Update one Clipnera machine: pull the branch, install missing packages,
# (re)write its systemd services and restart them. Run by deploy.sh, which
# passes the role and address. Both machines get YouTube cookies (exported
# from this computer's browser only when the server's copy is missing, near
# expiry or refused): the API reads links, the worker downloads the videos
# reels are made from. The API machine also applies database migrations.
#
# Settings are never stored on the machines: every service reads them from
# the env file at CONFIG_S3_URI with the machine's IAM role.
#
# Usage: bash update_ec2.sh <api|worker> <user@host>
# Env: CONFIG_S3_URI and AWS_REGION (required), EC2_KEY, GIT_BRANCH (default
# clipnera), COOKIE_BROWSER (default chrome), COOKIE_FILE (push this
# cookies.txt as-is), FORCE_COOKIES=1 (replace working cookies),
# COOKIE_MIN_DAYS (default 2), YOUTUBE_URL.
set -Eeuo pipefail

ROLE="${1:-}"
TARGET="${2:-}"
case "${ROLE}" in api|worker) ;; *) echo "Usage: bash update_ec2.sh <api|worker> <user@host>" >&2; exit 1 ;; esac
[[ -n "${TARGET}" ]] || { echo "Usage: bash update_ec2.sh <api|worker> <user@host>" >&2; exit 1; }
: "${CONFIG_S3_URI:?set CONFIG_S3_URI (deploy.sh reads it from deploy.env)}"
: "${AWS_REGION:?set AWS_REGION}"

REPO_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="${REPO_DIR}/backend"
COOKIE_FILE="${COOKIE_FILE:-}"
COOKIE_TMP_DIR=""
COOKIE_BROWSER="${COOKIE_BROWSER:-chrome}"
FORCE_COOKIES="${FORCE_COOKIES:-0}"
# Refresh the server's cookies once their sign-in expires within this many days.
COOKIE_MIN_DAYS="${COOKIE_MIN_DAYS:-2}"
# Any public video works; this one ("Me at the zoo", YouTube's first upload)
# has stayed up since 2005, so a failed check means cookies, not the video.
YOUTUBE_URL="${YOUTUBE_URL:-https://www.youtube.com/watch?v=jNQXAC9IVRw}"
EC2_KEY="${EC2_KEY:-${HOME}/Desktop/clipneras.pem}"
GIT_BRANCH="${GIT_BRANCH:-clipnera}"
[[ "${TARGET}" == *@* ]] || TARGET="ec2-user@${TARGET}"
EC2_USER="${TARGET%@*}"
EC2_HOST="${TARGET#*@}"
REMOTE_ROOT="/home/${EC2_USER}/clipnera_new"
# Kept outside the repo so git pull never touches it and it is never committed.
REMOTE_COOKIE="/home/${EC2_USER}/.clipnera/youtube_cookies.txt"
SSH_OPTS=(-i "${EC2_KEY}" -o IdentitiesOnly=yes -o ConnectTimeout=15 -o StrictHostKeyChecking=accept-new)

cleanup() {
    if [[ -n "${COOKIE_TMP_DIR}" ]]; then
        rm -rf -- "${COOKIE_TMP_DIR}"
    fi
}
trap cleanup EXIT

if [[ ! -f "${EC2_KEY}" ]]; then
    echo "EC2 key not found: ${EC2_KEY}" >&2
    exit 1
fi
if ! ssh "${SSH_OPTS[@]}" "${TARGET}" true; then
    echo "Cannot SSH to ${TARGET}. Is the instance running and port 22 open?" >&2
    exit 1
fi

# --- Cookies ---------------------------------------------------------------
# The backend writes YouTube's rotated cookies back to REMOTE_COOKIE after each
# use, so the copy on EC2 stays fresh by itself. Overwriting it on every deploy
# replaced those good cookies with a browser export that goes stale as soon as
# the browser rotates its session. Only push when the server's copy is missing,
# close to expiry or refused by YouTube, or when asked to.
cookies_valid_on_ec2() {
    ssh -T "${SSH_OPTS[@]}" "${TARGET}" bash -s -- \
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


def unix_seconds(raw: str) -> float:
    value = int(raw or 0)
    if value > 10**13:  # Chrome's format: microseconds since 1601
        return value / 1_000_000 - 11_644_473_600
    if value > 10**11:  # milliseconds
        return value / 1000
    return value


expiries = []
for line in open(path, encoding="utf-8", errors="ignore"):
    fields = line.removeprefix("#HttpOnly_").rstrip("\n").split("\t")
    if len(fields) == 7 and "youtube.com" in fields[0] and fields[5] in ("LOGIN_INFO", "__Secure-3PSID"):
        expiries.append(unix_seconds(fields[4]))
if not expiries:
    print("      cookies on EC2 are not signed in")
    sys.exit(1)
days_left = (min(expiries) - time.time()) / 86400
if days_left < min_days:
    print(f"      cookies on EC2 expire in {days_left:.1f} days")
    sys.exit(1)
print(f"      cookies on EC2 are valid for {days_left:.0f} more days")
PY

if ! ERR="$("${PYTHON}" -m yt_dlp --cookies "${COOKIE}" --js-runtimes deno --remote-components ejs:github \
    --skip-download --quiet --no-warnings --print '%(title)s' "${URL}" 2>&1 >/dev/null)"; then
    if grep -qE "Video unavailable|Private video|has been removed" <<<"${ERR}"; then
        echo "      Test video ${URL} is unavailable; set YOUTUBE_URL to a public video." >&2
        exit 2
    fi
    echo "      YouTube refused the cookies on EC2: $(tail -1 <<<"${ERR}")"
    exit 1
fi
CHECK_SCRIPT
}

PUSH_COOKIES=1
if [[ -n "${COOKIE_FILE}" || "${FORCE_COOKIES}" == "1" ]]; then
    echo "[1/3] Refreshing YouTube cookies as requested..."
else
    echo "[1/3] Checking YouTube cookies on EC2..."
    CHECK_STATUS=0
    cookies_valid_on_ec2 || CHECK_STATUS=$?
    if [[ "${CHECK_STATUS}" == "0" ]]; then
        PUSH_COOKIES=0
        echo "      Keeping them (set FORCE_COOKIES=1 to replace them anyway)."
    elif [[ "${CHECK_STATUS}" == "2" ]]; then
        exit 1  # the test video is gone; new cookies would not help
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
    echo "[2/3] Copying cookies to ${EC2_USER}@${EC2_HOST}:${REMOTE_COOKIE}..."
    ssh "${SSH_OPTS[@]}" "${TARGET}" "install -d -m 700 '$(dirname "${REMOTE_COOKIE}")'"
    scp -q "${SSH_OPTS[@]}" "${COOKIE_FILE}" "${EC2_USER}@${EC2_HOST}:${REMOTE_COOKIE}"
else
    echo "[2/3] Cookies on EC2 are still good; not copying."
fi

# --- Server update ---------------------------------------------------------
echo "[3/3] Updating code and packages, restarting services (${ROLE})..."
ssh -T "${SSH_OPTS[@]}" "${TARGET}" bash -s -- \
    "${ROLE}" "${GIT_BRANCH}" "${CONFIG_S3_URI}" "${AWS_REGION}" "${REMOTE_COOKIE}" "${YOUTUBE_URL}" <<'REMOTE_SCRIPT'
set -Eeuo pipefail

ROLE="$1"
GIT_BRANCH="$2"
CONFIG_S3_URI="$3"
REGION="$4"
REMOTE_COOKIE="$5"
YOUTUBE_URL="$6"
REMOTE_ROOT="${HOME}/clipnera_new"
BACKEND_DIR="${REMOTE_ROOT}/backend"
VENV_DIR="${BACKEND_DIR}/venv"
# What every service (and this script's own python calls) needs to find its
# settings in S3; nothing secret.
export CLIPNERA_CONFIG_S3_URI="${CONFIG_S3_URI}" AWS_DEFAULT_REGION="${REGION}" PYTHONPATH="${BACKEND_DIR}"
export PATH="${HOME}/.deno/bin:${PATH}"

cd "${REMOTE_ROOT}"
# Code edited in place on the server would block the pull; stash it so
# nothing is lost.
if ! git diff --quiet || ! git diff --cached --quiet; then
    git stash push -m "update_ec2: server edits $(date -u +%FT%TZ)"
    echo "WARNING: server had local code edits; stashed them (see: git stash list)." >&2
fi
git fetch -q origin "${GIT_BRANCH}"
git checkout -q "${GIT_BRANCH}"
git pull -q --ff-only origin "${GIT_BRANCH}"
cd "${BACKEND_DIR}"

if [[ ! -x "${VENV_DIR}/bin/python" ]]; then
    bash setup_ec2.sh
else
    bash scripts/install_deps.sh
fi

# The job worker renders reels: the graphics renderer's tools, the motion kit (icons, matte model) and the music
# library. Each step only fetches what is missing, and none of them can stop the deploy.
if [[ "${ROLE}" == "worker" ]]; then
    bash scripts/install_render_tools.sh || echo "WARNING: render tools not installed; reels render without graphics." >&2
    if [[ ! -f static/motion/kit/manifest.json ]]; then
        "${VENV_DIR}/bin/python" scripts/build_motion_kit.py --pull || "${VENV_DIR}/bin/python" scripts/build_motion_kit.py \
            || echo "WARNING: motion kit unavailable; graphics needing icons are skipped." >&2
    fi
    "${VENV_DIR}/bin/python" scripts/build_music_library.py || echo "WARNING: music library not fetched; reels use composed music." >&2
    "${VENV_DIR}/bin/python" scripts/build_asset_libraries.py \
        || echo "WARNING: sound, motion and emoji libraries not fetched; reels use the built-in set." >&2
fi

# Small machines (t3.micro: 1 GB) get swap so a burst cannot OOM-kill the API.
if [[ "$(awk '/MemTotal/ {print $2}' /proc/meminfo)" -lt 3000000 ]] && ! swapon --show | grep -q .; then
    sudo fallocate -l 2G /swapfile
    sudo chmod 600 /swapfile
    sudo mkswap /swapfile >/dev/null
    sudo swapon /swapfile
    grep -q '^/swapfile ' /etc/fstab || echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab >/dev/null
    echo "Added 2 GB swap."
fi

# Settings now come from S3 only; a leftover .env would silently override
# nothing but could leak, so it goes.
rm -f .env .env.production

# write_unit NAME DESCRIPTION LOG COMMAND [EXTRA_SERVICE_LINES]
write_unit() {
    sudo tee "/etc/systemd/system/$1.service" >/dev/null <<UNIT
[Unit]
Description=$2
After=network-online.target
Wants=network-online.target

[Service]
User=$(id -un)
WorkingDirectory=${BACKEND_DIR}
Environment=PATH=${HOME}/.deno/bin:/usr/local/bin:/usr/bin:/bin
Environment=PYTHONPATH=${BACKEND_DIR}
Environment=CLIPNERA_CONFIG_S3_URI=${CONFIG_S3_URI}
Environment=AWS_DEFAULT_REGION=${REGION}
# glibc gives every thread its own malloc arena and rarely returns them; with
# FFmpeg, ONNX and asyncio's thread pool that held hundreds of MB idle.
Environment=MALLOC_ARENA_MAX=2
ExecStart=${VENV_DIR}/bin/python $4
Restart=on-failure
RestartSec=5
StandardOutput=append:${BACKEND_DIR}/$3
StandardError=append:${BACKEND_DIR}/$3
${5:-}

[Install]
WantedBy=multi-user.target
UNIT
}

# Turns off a service this machine's role does not run.
disable_unit() {
    if systemctl list-unit-files "$1.service" >/dev/null 2>&1; then
        sudo systemctl disable --now --quiet "$1" 2>/dev/null || true
    fi
}

CONFIG_BUCKET="${CONFIG_S3_URI#s3://}"
# Brand and hook-bridge videos are kept out of git; both machines render
# exports, so both pull them from beside the settings file (deploy.sh uploads).
aws s3 sync "s3://${CONFIG_BUCKET%%/*}/motion/" "${BACKEND_DIR}/static/motion/" --only-show-errors

if [[ "${ROLE}" == "worker" ]]; then
    # Face-detection models are too large for git; they live beside the
    # settings file and only the worker (which renders) needs them.
    aws s3 sync "s3://${CONFIG_BUCKET%%/*}/models/" "${BACKEND_DIR}/models/" --only-show-errors
    disable_unit clipnera-backend
    disable_unit clipnera-publisher
    # The worker hands its running jobs back to the queue on SIGTERM; the next
    # start resumes each pipeline from its last finished step.
    write_unit clipnera-jobs "Clipnera background job worker" jobs.log "-m jobs.worker" \
        $'KillMode=mixed\nTimeoutStopSec=60'
    sudo systemctl daemon-reload
    sudo systemctl enable --quiet clipnera-jobs
    sudo systemctl restart clipnera-jobs
    sleep 5
    if systemctl is-active --quiet clipnera-jobs; then
        echo "Job worker running."
        exit 0
    fi
    echo "Job worker is not running. Last log lines:" >&2
    tail -40 jobs.log >&2 || true
    exit 1
fi

disable_unit clipnera-jobs
chmod 600 "${REMOTE_COOKIE}"
"${VENV_DIR}/bin/python" -m yt_dlp --cookies "${REMOTE_COOKIE}" --js-runtimes deno \
    --remote-components ejs:github --skip-download --quiet --print '%(title)s' "${YOUTUBE_URL}"

# Schema changes ship with the code; applied before the restart, so a failed
# migration leaves the running backend untouched. init_db also seeds the plans
# into an empty database.
"${VENV_DIR}/bin/python" init_db.py

# Stopping signals uvicorn alone, which finishes open requests first; the
# default also signalled their FFmpeg renders and failed every export in flight.
# Open requests get 10s: the browser's notifications stream never ends on its
# own, so without a limit every restart waited out the full stop timeout.
write_unit clipnera-backend "Clipnera backend" backend.log \
    "-m uvicorn main:app --host 0.0.0.0 --port 8000 --timeout-graceful-shutdown 10" $'KillMode=mixed\nTimeoutStopSec=60'
sudo systemctl daemon-reload
sudo systemctl enable --quiet clipnera-backend
sudo systemctl restart clipnera-backend

# The social publisher (python -m social.worker) refuses to start without a
# token key ring, so it only runs once one is configured.
if "${VENV_DIR}/bin/python" -c 'import sys; from core.config import get_settings; sys.exit(0 if get_settings().SOCIAL_TOKEN_ENCRYPTION_KEYS else 1)'; then
    write_unit clipnera-publisher "Clipnera social publisher" publisher.log "-m social.worker"
    sudo systemctl daemon-reload
    sudo systemctl enable --quiet clipnera-publisher
    sudo systemctl restart clipnera-publisher
else
    disable_unit clipnera-publisher
    echo "Social publisher off: SOCIAL_TOKEN_ENCRYPTION_KEYS is not set." >&2
fi

# HTTPS in front of the API, so the HTTPS frontend may call it. Caddy gets and
# renews a free Let's Encrypt certificate for <ip-with-dashes>.sslip.io, a
# hostname that resolves to this machine's Elastic IP.
IMDS_TOKEN="$(curl -fsS -X PUT http://169.254.169.254/latest/api/token -H 'X-aws-ec2-metadata-token-ttl-seconds: 60')"
PUBLIC_IP="$(curl -fsS -H "X-aws-ec2-metadata-token: ${IMDS_TOKEN}" http://169.254.169.254/latest/meta-data/public-ipv4)"
API_DOMAIN="${PUBLIC_IP//./-}.sslip.io"
if ! command -v caddy >/dev/null 2>&1; then
    curl -fsSL "https://caddyserver.com/api/download?os=linux&arch=amd64" -o /tmp/caddy
    sudo install -m 755 /tmp/caddy /usr/local/bin/caddy
    rm -f /tmp/caddy
fi
id caddy >/dev/null 2>&1 || sudo useradd --system --home-dir /var/lib/caddy --create-home --shell /sbin/nologin caddy
sudo install -d -m 755 /etc/caddy
printf '%s {\n\treverse_proxy 127.0.0.1:8000\n}\n' "${API_DOMAIN}" | sudo tee /etc/caddy/Caddyfile >/dev/null
sudo tee /etc/systemd/system/caddy.service >/dev/null <<UNIT
[Unit]
Description=Caddy (HTTPS for the Clipnera API)
After=network-online.target
Wants=network-online.target

[Service]
User=caddy
Environment=XDG_DATA_HOME=/var/lib/caddy XDG_CONFIG_HOME=/var/lib/caddy
ExecStart=/usr/local/bin/caddy run --config /etc/caddy/Caddyfile --adapter caddyfile
ExecReload=/usr/local/bin/caddy reload --config /etc/caddy/Caddyfile --adapter caddyfile
AmbientCapabilities=CAP_NET_BIND_SERVICE
Restart=on-failure

[Install]
WantedBy=multi-user.target
UNIT
sudo systemctl daemon-reload
sudo systemctl enable --quiet caddy
sudo systemctl restart caddy

for _ in {1..60}; do
    if curl -fsS http://127.0.0.1:8000/health >/dev/null 2>&1 && curl -fsS "https://${API_DOMAIN}/health" >/dev/null 2>&1; then
        echo "Backend healthy at https://${API_DOMAIN}: $(curl -fsS "https://${API_DOMAIN}/health")"
        exit 0
    fi
    sleep 2
done
echo "Backend or HTTPS did not become healthy. Last log lines:" >&2
tail -40 backend.log >&2
sudo journalctl -u caddy -n 20 --no-pager >&2
exit 1
REMOTE_SCRIPT

echo "Done: ${ROLE} on ${EC2_HOST}."
