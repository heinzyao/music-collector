#!/usr/bin/env bash
# Music Collector — Apple Music Token 取得與同步
#
# 新流程（不使用 Selenium 或 osascript token 擷取）：
#   1. 從 music.apple.com 取得 Developer Token
#   2. 啟動本機 HTTP 授權頁面（localhost:8765）
#   3. 開啟真實瀏覽器，使用者點擊授權按鈕完成 Apple ID 登入
#   4. MusicKit.authorize() 在真實瀏覽器中執行（無 bot 偵測問題）
#   5. Token 儲存至 data/apple_music_tokens.json
#   6. 執行完整同步
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
