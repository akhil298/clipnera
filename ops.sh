#!/usr/bin/env bash
# Day-to-day control of the Clipnera servers in Hyderabad (ap-south-2).
#
#   bash ops.sh status          what is running, addresses, API health
#   bash ops.sh stop            stop API server, worker and database (saves credits; site goes offline)
#   bash ops.sh start           start database and API server (the worker wakes itself when a job arrives)
#   bash ops.sh logs api        follow the API server's log (requests, errors)      Ctrl+C to quit
#   bash ops.sh logs worker     follow the worker's log (pipelines, renders, sleep)  Ctrl+C to quit
#   bash ops.sh ssh api|worker  open a shell on that server (starts the worker if it is asleep)
#
# Deploying new code is deploy.sh. Both read ~/.config/clipnera/deploy.env (no secrets).
set -Eeuo pipefail

CONFIG="${CLIPNERA_DEPLOY_CONFIG:-${HOME}/.config/clipnera/deploy.env}"
# shellcheck source=/dev/null
source "${CONFIG}"
: "${AWS_PROFILE:?}" "${AWS_REGION:?}" "${EC2_KEY:?}" "${API_HOST:?}" "${WORKER_INSTANCE_ID:?}"
export AWS_PROFILE AWS_REGION AWS_PAGER=""
DB_ID="${DB_ID:-clipnera-prod-db}"
SSH_OPTS=(-i "${EC2_KEY}" -o IdentitiesOnly=yes -o ConnectTimeout=10 -o StrictHostKeyChecking=accept-new)
API_IP="${API_HOST#*@}"
# Caddy serves the API over HTTPS at this sslip.io name (see update_ec2.sh).
API_URL="https://${API_IP//./-}.sslip.io"
LOGS="clipnera_new/backend"

api_instance_id() {
    aws ec2 describe-instances --filters Name=tag:Name,Values=clipnera-prod-api \
        "Name=instance-state-name,Values=pending,running,stopping,stopped" \
        --query 'Reservations[0].Instances[0].InstanceId' --output text
}

worker_address() {
    aws ec2 start-instances --instance-ids "${WORKER_INSTANCE_ID}" >/dev/null
    aws ec2 wait instance-running --instance-ids "${WORKER_INSTANCE_ID}"
    local ip
    ip="$(aws ec2 describe-instances --instance-ids "${WORKER_INSTANCE_ID}" \
        --query 'Reservations[0].Instances[0].PublicIpAddress' --output text)"
    for _ in {1..36}; do
        ssh "${SSH_OPTS[@]}" "ec2-user@${ip}" true 2>/dev/null && break
        sleep 5
    done
    echo "ec2-user@${ip}"
}

db_state() {
    aws rds describe-db-instances --db-instance-identifier "${DB_ID}" --query 'DBInstances[0].DBInstanceStatus' --output text
}

status() {
    aws ec2 describe-instances --instance-ids "$(api_instance_id)" "${WORKER_INSTANCE_ID}" \
        --query 'Reservations[].Instances[].[Tags[?Key==`Name`]|[0].Value,InstanceType,State.Name,PublicIpAddress]' --output table
    echo "Database ${DB_ID}: $(db_state)"
    echo "API health: $(curl -s -m 5 "${API_URL}/health" || echo 'not answering')"
}

case "${1:-status}" in
    status) status ;;
    stop)
        echo "Stopping API server and worker..."
        aws ec2 stop-instances --instance-ids "$(api_instance_id)" "${WORKER_INSTANCE_ID}" >/dev/null
        if [[ "$(db_state)" == "available" ]]; then
            # RDS starts a stopped database again by itself after 7 days.
            echo "Stopping database (AWS restarts it automatically after 7 days)..."
            aws rds stop-db-instance --db-instance-identifier "${DB_ID}" >/dev/null
        fi
        aws ec2 wait instance-stopped --instance-ids "$(api_instance_id)" "${WORKER_INSTANCE_ID}"
        status
        ;;
    start)
        if [[ "$(db_state)" == "stopped" ]]; then
            echo "Starting database (takes a few minutes)..."
            aws rds start-db-instance --db-instance-identifier "${DB_ID}" >/dev/null
        fi
        echo "Starting API server..."
        aws ec2 start-instances --instance-ids "$(api_instance_id)" >/dev/null
        aws rds wait db-instance-available --db-instance-identifier "${DB_ID}"
        aws ec2 wait instance-running --instance-ids "$(api_instance_id)"
        # The API may have booted before the database was up; restart it now that it is.
        for _ in {1..36}; do
            ssh "${SSH_OPTS[@]}" "${API_HOST}" 'sudo systemctl restart clipnera-backend caddy' 2>/dev/null && break
            sleep 5
        done
        for _ in {1..30}; do
            curl -fs -m 5 "${API_URL}/health" >/dev/null && break
            sleep 5
        done
        status
        ;;
    logs)
        case "${2:-api}" in
            api) ssh -t "${SSH_OPTS[@]}" "${API_HOST}" "tail -n 100 -F ${LOGS}/backend.log ${LOGS}/publisher.log 2>/dev/null" ;;
            worker) ssh -t "${SSH_OPTS[@]}" "$(worker_address)" "tail -n 100 -F ${LOGS}/jobs.log" ;;
            *) echo "Usage: bash ops.sh logs api|worker" >&2; exit 1 ;;
        esac
        ;;
    ssh)
        case "${2:-api}" in
            api) ssh "${SSH_OPTS[@]}" "${API_HOST}" ;;
            worker) ssh "${SSH_OPTS[@]}" "$(worker_address)" ;;
            *) echo "Usage: bash ops.sh ssh api|worker" >&2; exit 1 ;;
        esac
        ;;
    *) sed -n '2,12p' "$0"; exit 1 ;;
esac
