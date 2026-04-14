#!/usr/bin/env bash
# Music Collector — Apple Music 手動登入初始化腳本
# 用法：
#   ./bootstrap-apple-music-login.sh

set -euo pipefail

cd "$(dirname "$0")"

PROFILE_DIR="$(pwd)/data/browser_profile"
mkdir -p "$PROFILE_DIR"

open -na "Google Chrome" --args \
  --user-data-dir="$PROFILE_DIR" \
  --profile-directory=Default \
  --new-window \
  "https://music.apple.com/"

printf "\nOpened Apple Music in a normal Chrome window using the shared profile.\n"
printf "Please finish Apple login there, then return here and run ./sync-apple-music.sh\n"
