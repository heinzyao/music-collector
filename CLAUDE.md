# Music Collector — 專案指引

## 專案概述

自動從 10 個音樂評論網站蒐集推薦曲目，透過 Spotify API 建立播放清單。

## 開發指令

```bash
# 安裝依賴
uv sync

# 乾跑測試（不需 Spotify 憑證）
./run.sh --dry-run

# 完整執行（需 .env 中的 Spotify 憑證）
./run.sh

# 查看近期蒐集紀錄
./run.sh --recent 7

# 檢視備份（列出所有 / 指定季度）
./run.sh --backup
./run.sh --backup Q1

# 匯出備份供 Apple Music 匯入
./run.sh --export Q1              # 匯出為 CSV（適用 TuneMyMusic）
./run.sh --export Q1 --format txt # 匯出為純文字
./run.sh --export Q1 --all        # 包含未在 Spotify 找到的曲目

# 自動匯入 Apple Music（開啟瀏覽器，需手動登入 Apple ID）
./run.sh --import Q1

# 清除歌單與資料庫，重新蒐集
./run.sh --reset
```

> `run.sh` 等同 `PYTHONPATH=src uv run python -m music_collector`。

## 架構要點

- `src/music_collector/scrapers/base.py` — `BaseScraper` 抽象類別與 `Track` 資料模型
- `src/music_collector/scrapers/__init__.py` — `ALL_SCRAPERS` 註冊表，新增擷取器需在此註冊
- `src/music_collector/spotify.py` — Spotify 整合（搜尋驗證、播放清單管理、季度歸檔）
- `src/music_collector/db.py` — SQLite 去重，以 `(artist, title)` 為唯一鍵
- `src/music_collector/backup.py` — 季度 JSON 備份至 `data/backups/YYYY/QN.json`
- `src/music_collector/export.py` — 匯出備份為 CSV/TXT，供 Apple Music 匯入工具使用
- `src/music_collector/tunemymusic.py` — Selenium 自動化 TuneMyMusic 匯入 Apple Music
- `src/music_collector/notify.py` — LINE Messaging API 通知（Channel ID + Secret 自動產生 Token）
- `src/music_collector/main.py` — 主流程與 CLI

### 擷取器技術細節

| 擷取器 | 方式 | 解析策略 |
|--------|------|----------|
| Pitchfork | HTML | `div[class*='SummaryItemWrapper']` 容器，`h3` 取曲名，`div sub-hed` 取藝人 |
| NME | HTML | `/reviews/track` 頁面，敘述性標題解析（所有格 + 動詞短語分離） |
| SPIN | HTML | `/new-music/` 頁面，typographic 引號匹配 + 動詞短語分離 |
| Consequence | HTML | 引號提取曲名 + `_extract_artist_from_prefix()` 動詞邊界偵測 |
| Line of Best Fit | HTML | 所有格 `'s` 優先策略 + 擴展動詞清單 |
| Slant/Complex/RA | HTML | 含 JS 渲染偵測（Cloudflare/Next.js 空頁面檢查） |

### 引號處理注意事項

- Consequence：不可將直引號 `'` 放入引號匹配字元集，否則所有格會被誤判為開引號
- NME / SPIN：使用 `\u2019(?![a-zA-Z])` negative lookahead 避免將縮寫撇號（如 Where's）誤判為結尾引號
- SPIN：引號內曲名需 `rstrip(".,;:!?")` 移除尾端標點

## 新增擷取器

1. 在 `src/music_collector/scrapers/` 建立新檔案
2. 繼承 `BaseScraper`，實作 `fetch_tracks()` 回傳 `list[Track]`
3. 在 `scrapers/__init__.py` 的 `ALL_SCRAPERS` 中註冊
4. 用 `--dry-run` 測試

## 注意事項

- `.env`、`.spotify_cache`、`data/` 不可推送至 Git
- 每個擷取器必須獨立處理例外，不可影響其他來源
- Spotify 搜尋先用精確查詢 `track: artist:`，失敗後再用寬鬆查詢，兩者皆需通過藝人 + 曲名雙重驗證
- 曲目去重以大小寫不敏感的 `(artist, title)` 比對
- 備份/通知各自 try/except，失敗不影響主流程
- `--dry-run` 模式不觸發 Spotify 操作、備份與通知
