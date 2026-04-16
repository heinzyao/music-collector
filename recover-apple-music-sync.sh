#!/usr/bin/env bash
# Music Collector — Apple Music 兩段式恢復流程
# 用法：
#   ./recover-apple-music-sync.sh

set -euo pipefail

cd "$(dirname "$0")"

SUMMARY_LOG="$(pwd)/data/apple_music_recovery.log"
PROFILE_DIR="$(pwd)/data/browser_profile"
mkdir -p "$(dirname "$SUMMARY_LOG")"

log_summary() {
  printf "%s %s\n" "$(date '+%Y-%m-%d %H:%M:%S')" "$1" | tee -a "$SUMMARY_LOG"
}

# 關閉佔用 browser profile 的 Chrome 進程（從 SingletonLock 讀取 PID）
close_bootstrap_chrome() {
  local singleton="$PROFILE_DIR/SingletonLock"
  if [ ! -L "$singleton" ]; then
    return 0
  fi

  local lock_target
  lock_target=$(readlink "$singleton" 2>/dev/null || true)
  local chrome_pid="${lock_target##*-}"

  if [ -n "$chrome_pid" ] && kill -0 "$chrome_pid" 2>/dev/null; then
    printf "Closing bootstrap Chrome (PID %s)...\n" "$chrome_pid"
    kill "$chrome_pid" 2>/dev/null || true
    sleep 2
  fi

  # 移除殘留 lock 檔（Chrome 退出後有時不清理）
  rm -f "$PROFILE_DIR/SingletonLock" \
        "$PROFILE_DIR/SingletonCookie" \
        "$PROFILE_DIR/SingletonSocket" 2>/dev/null || true
}

printf "\n[1/3] Opening Apple Music login bootstrap...\n"
log_summary "[INFO] Recovery flow started"
./bootstrap-apple-music-login.sh

printf "\n============================================================\n"
printf "Apple Music login window has been opened in normal Chrome.\n"
printf "1. Complete Apple login in that Chrome window.\n"
printf "2. Return to THIS Terminal window and press Enter.\n"
printf "   (The script will automatically close the Chrome window.)\n"
printf "============================================================\n"
printf "\nPress Enter after completing Apple login..."
read -r _

printf "\nClosing bootstrap Chrome and cleaning up profile locks...\n"
close_bootstrap_chrome
sleep 1

printf "\n[2/3] Validating shared Apple Music session...\n"
if ! PYTHONPATH=src uv run python -m music_collector --check-apple-music-session; then
  log_summary "[WARN] Session validation failed"
  printf "\nApple Music session is still not ready.\n"
  printf "Please confirm that you completed login in the normal Chrome window,\n"
  printf "then run Music Collector Apple Music Recovery.app again.\n"
  exit 1
fi

log_summary "[INFO] Session validation passed"
printf "\n[3/3] Session looks good. Starting Apple Music sync...\n"
if ./sync-apple-music.sh; then
  log_summary "[INFO] Apple Music sync completed successfully"
  printf "\nRecovery flow completed successfully.\n"
else
  log_summary "[ERROR] Apple Music sync failed"
  printf "\nRecovery flow finished, but Apple Music sync failed.\n"
  printf "Please review the Terminal output above for the exact sync error.\n"
  exit 1
fi
