#!/usr/bin/env bash
# Deploy the latest pushed code to both machines: the API machine first, then
# the job worker. Each pulls the branch, installs only missing packages
# (backend/scripts/install_deps.sh) and restarts its services; the API machine
# also applies migrations.
#
# The worker powers itself off when idle, so it is started for the deploy and
# goes back to sleep on its own once it has had no jobs for a while.
#
# Usage: bash deploy.sh [api|worker]   (default: both)
# Reads ~/.config/clipnera/deploy.env (override with CLIPNERA_DEPLOY_CONFIG),
# which holds no secrets:
#   AWS_PROFILE=...  AWS_REGION=ap-south-2  EC2_KEY=/path/to/key.pem
#   API_HOST=ec2-user@<api address>  WORKER_INSTANCE_ID=i-...
#   CONFIG_S3_URI=s3://<config bucket>/clipnera.env  (the servers' settings)
# Cookie options (FORCE_COOKIES=1, COOKIE_FILE=...) pass through to the API
# machine, e.g. FORCE_COOKIES=1 bash deploy.sh api to replace its cookies.
set -Eeuo pipefail

REPO_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
CONFIG="${CLIPNERA_DEPLOY_CONFIG:-${HOME}/.config/clipnera/deploy.env}"
TARGET="${1:-both}"

if [[ ! -f "${CONFIG}" ]]; then
    echo "Missing ${CONFIG}; see the header of this script." >&2
    exit 1
fi
# shellcheck source=/dev/null
source "${CONFIG}"
: "${AWS_PROFILE:?set in ${CONFIG}}" "${AWS_REGION:?set in ${CONFIG}}" "${EC2_KEY:?set in ${CONFIG}}"
: "${API_HOST:?set in ${CONFIG}}" "${WORKER_INSTANCE_ID:?set in ${CONFIG}}" "${CONFIG_S3_URI:?set in ${CONFIG}}"
export AWS_PROFILE AWS_REGION EC2_KEY CONFIG_S3_URI AWS_PAGER=""
SSH_OPTS=(-i "${EC2_KEY}" -o IdentitiesOnly=yes -o ConnectTimeout=5 -o StrictHostKeyChecking=accept-new)
CONFIG_BUCKET="${CONFIG_S3_URI#s3://}"
CONFIG_BUCKET="${CONFIG_BUCKET%%/*}"

# Brand and hook-bridge videos stay out of git; the servers pull them from
# s3://<config bucket>/motion/ (see update_ec2.sh), so upload this computer's
# copies first. Unchanged files are skipped.
upload_motion() {
    echo "=== Motion videos -> s3://${CONFIG_BUCKET}/motion/ ==="
    aws s3 sync "${REPO_DIR}/backend/static/motion/" "s3://${CONFIG_BUCKET}/motion/" --only-show-errors \
        --exclude '*' --include 'branding/*.mp4' --include 'hook_graphics/*.mp4'
}

deploy_api() {
    echo "=== API machine (${API_HOST}) ==="
    bash "${REPO_DIR}/update_ec2.sh" api "${API_HOST}"
}

deploy_worker() {
    echo "=== Worker machine (${WORKER_INSTANCE_ID}) ==="
    aws ec2 start-instances --instance-ids "${WORKER_INSTANCE_ID}" >/dev/null
    aws ec2 wait instance-running --instance-ids "${WORKER_INSTANCE_ID}"
    local ip
    ip="$(aws ec2 describe-instances --instance-ids "${WORKER_INSTANCE_ID}" \
        --query 'Reservations[0].Instances[0].PublicIpAddress' --output text)"
    # sshd answers a little after EC2 reports "running".
    for _ in {1..36}; do
        ssh "${SSH_OPTS[@]}" "ec2-user@${ip}" true 2>/dev/null && break
        sleep 5
    done
    # Stop the worker first: its idle timer must not power the machine off
    # halfway through the package install.
    ssh "${SSH_OPTS[@]}" "ec2-user@${ip}" 'sudo systemctl stop clipnera-jobs 2>/dev/null || true'
    bash "${REPO_DIR}/update_ec2.sh" worker "ec2-user@${ip}"
}

upload_motion
case "${TARGET}" in
    api) deploy_api ;;
    worker) deploy_worker ;;
    both) deploy_api; deploy_worker ;;
    *) echo "Usage: bash deploy.sh [api|worker]" >&2; exit 1 ;;
esac
