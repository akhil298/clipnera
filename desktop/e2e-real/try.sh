#!/usr/bin/env bash
# Try the Mac app by hand against the real backend and real AI: starts a throwaway backend
# (see stack.sh), then opens the app already signed in as its test user, with live reload.
# Close the app (or press Ctrl+C) to stop everything.
#
#   desktop/e2e-real/try.sh
set -euo pipefail
source "$(dirname "$0")/stack.sh"

cd "$here/.."
CLIPNERA_API_URL="$api_url" CLIPNERA_DEV_TOKEN="$token" npm run dev
