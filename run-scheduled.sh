#!/usr/bin/env bash
# Music Collector — 每週排程腳本
#
# 流程：擷取 → Spotify 搜尋 → All Time 累積歌單鏡射 → 備份 → 季度歸檔 → 通知

set -uo pipefail

cd "$(dirname "$0")"

# Playwright 升版後瀏覽器需重新下載（冪等，已安裝時秒過）；失敗不擋其他爬蟲
uv run playwright install chromium || true

PYTHONPATH=src uv run python -m music_collector
