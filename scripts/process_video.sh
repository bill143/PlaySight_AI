#!/usr/bin/env bash
# process_video.sh - Process one match video end-to-end (detect -> track ->
# identify -> events -> stats -> reports). Thin wrapper around `playsight process`.
#
# Usage:
#   ./scripts/process_video.sh data/demo/demo_match.mp4
#   ./scripts/process_video.sh match.mp4 --match-id <id> --club my-club
#   ./scripts/process_video.sh match.mp4 --no-eager   # use a Celery worker
#
# Requires the package installed in the active environment: pip install -e ".[dev]"

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

if [[ $# -lt 1 ]]; then
    echo "Usage: $0 VIDEO [--match-id ID] [--club CLUB] [--no-eager]" >&2
    exit 2
fi

VIDEO="$1"
shift

if [[ ! -f "$VIDEO" ]]; then
    echo "ERROR: Video not found: $VIDEO" >&2
    exit 1
fi

exec playsight process "$VIDEO" "$@"
