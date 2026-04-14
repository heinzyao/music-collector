#!/usr/bin/env bash
# Music Collector — Apple Music 兩段式恢復流程
# 用法：
#   ./recover-apple-music-sync.sh

set -euo pipefail

cd "$(dirname "$0")"

printf "\n[1/3] Opening Apple Music login bootstrap...\n"
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
  printf "\nApple Music session is still not ready.\n"
  printf "Please confirm that you completed login in the normal Chrome window,\n"
  printf "then run Music Collector Apple Music Recovery.app again.\n"
  exit 1
fi

printf "\n[3/3] Session looks good. Starting Apple Music sync...\n"
./sync-apple-music.sh

printf "\nRecovery flow completed.\n"
