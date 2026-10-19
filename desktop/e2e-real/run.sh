#!/usr/bin/env bash
# The real end-to-end run: the Mac app edits a real video with the real backend and real AI,
# driven by Playwright. The backend is a throwaway one (see stack.sh).
#
#   desktop/e2e-real/run.sh path/to/video-with-speech.mp4 [spec, e.g. full-edit]
set -euo pipefail
video="$(cd "$(dirname "$1")" && pwd)/$(basename "$1")"
source "$(dirname "$0")/stack.sh"

mkdir -p "$work/run"
cd "$here/.."
REAL_API_URL="$api_url" REAL_TOKEN="$token" REAL_VIDEO="$video" REAL_OUT="$work/run" npm run test:real -- "${@:2}"
echo "What happened: $work/run/result.json and the screenshots next to it. Backend log: $work/backend.log"
