#!/usr/bin/env bash
# Music Collector — 手動 Apple Music 同步腳本
# 用法：
#   ./sync-apple-music.sh

set -euo pipefail

cd "$(dirname "$0")"
PYTHONPATH=src exec uv run python -m music_collector --apple-music
