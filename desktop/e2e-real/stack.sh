# Starts a throwaway backend for the Mac app: its own Postgres (port 5433), a local S3
# (moto, port 5055) and the backend (port 8766), with one signed-in test user who has the
# AI editor on and credits. Your database and S3 bucket are never used; the AI keys and
# model list come from backend/.env as they are.
#
# Sourced by run.sh and try.sh. Afterwards: $work is the temp folder, $api_url the backend, $token the user's
# session token, and everything stops when the calling script exits.
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# Other ports let a second stack run beside one already up: PG_PORT=5434 S3_PORT=5056 API_PORT=8767.
pg_port="${PG_PORT:-5433}" s3_port="${S3_PORT:-5055}" api_port="${API_PORT:-8766}"
api_url="http://localhost:$api_port"
for port in "$pg_port" "$s3_port" "$api_port"; do
  if lsof -iTCP:"$port" -sTCP:LISTEN >/dev/null 2>&1; then
    echo "Port $port is in use (an earlier run still up?). Stop it with: lsof -ti tcp:$port | xargs kill" >&2
    exit 1
  fi
done
backend="$here/../../backend"
work="$(mktemp -d -t clipnera-real-e2e)"
python="$backend/venv/bin/python"
echo "Working in $work"

cleanup() {
  [ -n "${api:-}" ] && kill "$api" 2>/dev/null || true
  [ -n "${s3:-}" ] && kill "$s3" 2>/dev/null || true
  /opt/homebrew/bin/pg_ctl -D "$work/pg" stop -m fast >/dev/null 2>&1 || true
}
trap cleanup EXIT

# Postgres, with no unix socket (temp paths are too long for one on macOS).
/opt/homebrew/bin/initdb -D "$work/pg" -U postgres --auth=trust >/dev/null
/opt/homebrew/bin/pg_ctl -D "$work/pg" -o "-p $pg_port -c unix_socket_directories='' -c listen_addresses=127.0.0.1" -l "$work/pg.log" start >/dev/null
sleep 2
/opt/homebrew/bin/psql -h 127.0.0.1 -p "$pg_port" -U postgres -qc "create database clipnera_e2e"

# A local S3. localhost.localstack.cloud resolves to 127.0.0.1, so the backend's
# virtual-host presigned URLs work against it.
"$python" -m pip install -q --target "$work/moto" "moto[server,s3]" 2>/dev/null
MOTO_S3_CUSTOM_ENDPOINTS="http://s3.localhost.localstack.cloud:$s3_port" PYTHONPATH="$work/moto" \
  "$python" -m moto.server -H 127.0.0.1 -p "$s3_port" >"$work/moto.log" 2>&1 &
s3=$!
sleep 3

export DATABASE_URL="postgresql+asyncpg://postgres@127.0.0.1:$pg_port/clipnera_e2e"
export LOCALSTACK_ENDPOINT="http://s3.localhost.localstack.cloud:$s3_port"
export S3_BUCKET_NAME="clipnera-e2e" AWS_REGION="us-east-1" AWS_ACCESS_KEY_ID="test" AWS_SECRET_ACCESS_KEY="test"
export PUBLIC_API_URL="$api_url" SECRET_KEY="clipnera-e2e-only-secret" JOB_QUEUE_BACKEND="inprocess" LLM_MODE="live"

(cd "$backend" && "$python" -c "
import boto3
boto3.client('s3', region_name='us-east-1', aws_access_key_id='test', aws_secret_access_key='test', endpoint_url='$LOCALSTACK_ENDPOINT').create_bucket(Bucket='clipnera-e2e')")
(cd "$backend" && PYTHONPATH=. "$python" "$here/setup_db.py" "$work/token.txt")
token="$(cat "$work/token.txt")"

# exec: $! is uvicorn itself, so the cleanup stops it (not just the subshell).
(cd "$backend" && exec "$backend/venv/bin/uvicorn" main:app --port "$api_port" >"$work/backend.log" 2>&1) &
api=$!
for _ in $(seq 1 60); do curl -s -m 1 -o /dev/null "$api_url/docs" && break; sleep 1; done
echo "Backend on $api_url (log: $work/backend.log)"
