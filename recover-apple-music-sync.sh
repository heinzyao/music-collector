#!/usr/bin/env bash
# Music Collector — Apple Music Token 取得與同步 (已升級為手動匯出)
#
# 用法：
#   ./recover-apple-music-sync.sh

set -euo pipefail

cd "$(dirname "$0")"

printf "\n============================================================\n"
printf "💡 溫馨提示：Apple Music 匯入機制已調整為「手動匯出」模式 💡\n"
printf "============================================================\n"
printf "本專案已移除複雜且容易過期的 Apple Music API 自動登入與 cookie 同步。\n"
printf "現在已不再需要調整 Safari 的 JavaScript 設定，也不再需要下載 Token！\n\n"
printf "新機制將直接為您產出 macOS 音樂 (Music) App 可完美識別的手動匯入文字檔 (.txt)。\n\n"
printf "👉 您可以直接執行以下同步腳本來生成匯入檔案：\n"
printf "   ./sync-apple-music.sh\n"
printf "============================================================\n\n"

read -p "是否直接執行 ./sync-apple-music.sh 開始產出歌單？(Y/N): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
  exec ./sync-apple-music.sh
fi
