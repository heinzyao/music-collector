#!/usr/bin/env bash
# Music Collector — Apple Music Token 取得與同步
#
# 流程（Safari cookie 路線）：
#   1. 從 Safari 的 music.apple.com 分頁讀取 media-user-token cookie
#   2. 從 Apple Music Vite bundle 提取 developerToken
#   3. Token 儲存至 data/apple_music_tokens.json
#   4. 執行完整同步
#
# 前置條件（一次性設定）：
#   - Safari → 偏好設定 → 進階 → 勾選「在選單列中顯示開發選單」
#   - Safari → 開發 → 勾選「允許 JavaScript 從 Apple 事件執行」
#   - 在 Safari 開啟 music.apple.com 並完成 Apple ID 登入
#
# 用法：
#   ./recover-apple-music-sync.sh

set -euo pipefail

cd "$(dirname "$0")"

SUMMARY_LOG="$(pwd)/data/apple_music_recovery.log"
mkdir -p "$(dirname "$SUMMARY_LOG")"

log_summary() {
  printf "%s %s\n" "$(date '+%Y-%m-%d %H:%M:%S')" "$1" | tee -a "$SUMMARY_LOG"
}

log_summary "[INFO] Recovery flow started"

printf "\n[1/2] Starting Apple Music authorization (local auth server)...\n\n"

if PYTHONPATH=src uv run python -m music_collector.apple_music.auth_server; then
  log_summary "[INFO] Apple Music token obtained successfully"
else
  log_summary "[ERROR] Failed to obtain Apple Music token"
  printf "\n[ERROR] 授權未完成，無法取得 Token。\n"
  printf "        請重試，並確認在授權頁面點擊「授權 Apple Music」後完成 Apple ID 登入。\n"
  exit 1
fi

printf "\n[2/2] Starting Apple Music sync...\n\n"
if ./sync-apple-music.sh; then
  log_summary "[INFO] Apple Music sync completed successfully"
  printf "\nRecovery flow completed successfully.\n"
else
  log_summary "[ERROR] Apple Music sync failed"
  printf "\nSync failed. Please review the output above for details.\n"
  exit 1
fi
