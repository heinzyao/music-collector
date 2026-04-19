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

printf "\n============================================================\n"
printf "Apple Music 已在 Chrome 視窗中開啟（使用獨立的 browser profile）\n"
printf "============================================================\n"
printf "\n[重要] 請在該 Chrome 視窗中完成以下步驟：\n"
printf "  1. 點擊右上角「登入」按鈕（Sign In）\n"
printf "  2. 輸入 Apple ID 電子郵件 → 密碼 → 雙重認證碼（2FA）\n"
printf "  3. 確認看到你的頭像或個人資料出現在右上角（這是登入成功的標誌）\n"
printf "  4. 頭像出現後，請再多等 5 秒讓頁面完全載入，再回終端機按 Enter\n"
printf "  5. 不要手動關閉 Chrome 視窗，腳本會自動處理\n"
printf "\n注意：系統層的 Apple ID 登入（iCloud 設定）不等於 Apple Music 網頁登入。\n"
printf "      必須在此 Chrome 視窗中點擊 Sign In 並走完授權流程才算完成。\n\n"
