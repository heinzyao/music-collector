#!/usr/bin/env bash
# Music Collector — Apple Music 兩段式恢復流程
# 用法：
#   ./recover-apple-music-sync.sh

set -euo pipefail

cd "$(dirname "$0")"

SUMMARY_LOG="$(pwd)/data/apple_music_recovery.log"
mkdir -p "$(dirname "$SUMMARY_LOG")"

log_summary() {
  printf "%s %s\n" "$(date '+%Y-%m-%d %H:%M:%S')" "$1" | tee -a "$SUMMARY_LOG"
}

printf "\n[1/3] Opening Apple Music login bootstrap...\n"
log_summary "[INFO] Recovery flow started"
./bootstrap-apple-music-login.sh

printf "\n============================================================\n"
printf "Apple Music login window has been opened in normal Chrome.\n"
printf "1. Complete Apple login in that Chrome window.\n"
printf "2. Return to THIS Terminal window.\n"
printf "3. Press Enter here to validate the shared session and continue sync.\n"
printf "============================================================\n"
printf "\nPress Enter here after Apple login is finished..."
read -r _

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
