#!/usr/bin/env bash
# Music Collector — 每日排程腳本（含 Apple Music 同步）
#
# 流程：
#   1. 擷取 → Spotify 搜尋 → 備份 → 通知
#   2. Apple Music 同步（session 有效時自動匯入，無效時 LINE 通知需重新登入）
#
# 即使第一階段失敗，Apple Music 同步仍會嘗試執行（同步既有歌單）。

set -uo pipefail

cd "$(dirname "$0")"

PYTHONPATH=src uv run python -m music_collector
PYTHONPATH=src uv run python -m music_collector --apple-music || true
