#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 1 ]]; then
  cat <<'USAGE'
Usage: scripts/process_video.sh <video-path> [output-dir]

Process a single video through the PlaySight AI CLI.

Arguments:
  <video-path>   Path to the input video file
  [output-dir]   Optional output directory (default: data/outputs)
USAGE
  exit 1
fi

VIDEO_PATH="$1"
OUTPUT_DIR="${2:-data/outputs}"

if [[ ! -f "$VIDEO_PATH" ]]; then
  echo "Error: video file not found: $VIDEO_PATH" >&2
  exit 1
fi

python backend/cli.py process-video "$VIDEO_PATH" --output-dir "$OUTPUT_DIR"
