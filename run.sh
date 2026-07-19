#!/usr/bin/env bash
# Music Collector — 手動執行腳本
# 用法：
#   ./run.sh              完整執行
#   ./run.sh --dry-run    僅擷取，不寫入 Spotify
#   ./run.sh --backup     列出備份
#   ./run.sh --backup Q1  檢視 Q1 備份內容
#   ./run.sh --recent 7   查看近 7 天紀錄
#   ./run.sh --reset      清除歌單重新蒐集

cd "$(dirname "$0")"

# Playwright 升版後瀏覽器需重新下載（冪等，已安裝時秒過）；失敗不擋其他爬蟲
uv run playwright install chromium || true

PYTHONPATH=src exec uv run python -m music_collector "$@"
