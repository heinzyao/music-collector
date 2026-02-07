# Music Collector — 專案指引

## 專案概述

自動從 10 個音樂評論網站蒐集推薦曲目，透過 Spotify API 建立播放清單。

## 開發指令

```bash
# 安裝依賴
uv sync

# 乾跑測試（不需 Spotify 憑證）
PYTHONPATH=src uv run python -m music_collector --dry-run

# 完整執行（需 .env 中的 Spotify 憑證）
PYTHONPATH=src uv run python -m music_collector

# 查看近期蒐集紀錄
PYTHONPATH=src uv run python -m music_collector --recent 7
```

## 架構要點

- `src/music_collector/scrapers/base.py` — `BaseScraper` 抽象類別與 `Track` 資料模型
- `src/music_collector/scrapers/__init__.py` — `ALL_SCRAPERS` 註冊表，新增擷取器需在此註冊
- `src/music_collector/spotify.py` — Spotify 整合（搜尋驗證、播放清單管理、季度歸檔）
- `src/music_collector/db.py` — SQLite 去重，以 `(artist, title)` 為唯一鍵
- `src/music_collector/backup.py` — 季度 JSON 備份至 `data/backups/YYYY/QN.json`
- `src/music_collector/notify.py` — LINE Messaging API 通知（Channel ID + Secret 自動產生 Token）
- `src/music_collector/main.py` — 主流程：擷取 → 去重 → 合併舊清單 → 季度歸檔 → 搜尋 → 加入播放清單 → 備份 → 通知

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
