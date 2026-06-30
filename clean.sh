#!/usr/bin/env bash
# Music Collector — 磁碟空間優化與清理腳本
#
# 用法：
#   ./clean.sh             # 實際執行清理
#   ./clean.sh --dry-run   # 預演清理（不實際刪除）

set -euo pipefail

cd "$(dirname "$0")"

# 確保虛擬環境可用，若不可用則用 python 代替
if command -v uv &> /dev/null; then
  PYTHON_CMD="uv run python"
else
  PYTHON_CMD="python"
fi

# 執行 Python 清理模組
PYTHONPATH=src $PYTHON_CMD -m music_collector --clean "$@"
