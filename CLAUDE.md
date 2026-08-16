# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 專案概述

自動從 13 個音樂評論網站蒐集推薦曲目，同步至 Spotify 播放清單。Apple Music 由 Soundiiz Auto-Sync 從 Spotify 端鏡射，專案本身不含 Apple Music 程式碼。

## 開發指令

```bash
# 安裝依賴（含 Playwright，Resident Advisor 需要）
uv sync --extra browser

# 安裝 Playwright Chromium 瀏覽器（uv sync 後執行；playwright 升版後需重跑，
# run.sh / run-scheduled.sh 已內建此步驟自動補裝）
uv run playwright install chromium

# 安裝含測試工具
uv sync --extra test

# 乾跑測試（不需 Spotify 憑證）
./run.sh --dry-run

# 完整執行（需 .env 中的 Spotify 憑證）
./run.sh

# 查看近期蒐集紀錄
./run.sh --recent 7

# 回填「Critics' Picks — All Time」累積歌單（主歌單 + 所有季度歸檔，去重）
./run.sh --backfill-all-time

# 輸出主歌單與 All Time 歌單的 Spotify 連結（設定 Soundiiz 時使用）
./run.sh --export-spotify-url

# 執行測試（全部）
PYTHONPATH=src uv run pytest tests/ -q

# 執行單一測試檔案
PYTHONPATH=src uv run pytest tests/test_spotify.py -v

# 執行單一測試
PYTHONPATH=src uv run pytest tests/test_spotify.py::test_mirror_to_all_time_skips_existing_uris -v
```

> `run.sh` 等同 `PYTHONPATH=src uv run python -m music_collector`。

## 架構要點

- `src/music_collector/scrapers/base.py` — `BaseScraper` 抽象類別、`Track` 資料模型、`_get_rendered()` Playwright 方法
- `src/music_collector/scrapers/__init__.py` — `ALL_SCRAPERS` 註冊表（13 個擷取器）
- `src/music_collector/health.py` — `record_scrape_result()`、`get_unhealthy_sources()`、`get_health_report()`
- `src/music_collector/spotify.py` — Spotify 整合（搜尋驗證、播放清單管理、季度歸檔、All Time 累積歌單）
- `src/music_collector/db.py` — SQLite 去重，以 `(artist, title)` 為唯一鍵
- `src/music_collector/backup.py` — 季度 JSON 備份至 `data/backups/YYYY/QN.json`
- `src/music_collector/export.py` — 季度備份匯出為 CSV/TXT；`export_spotify_url()` 輸出歌單連結
- `src/music_collector/notify.py` — LINE + Telegram + Slack 多通道通知
- `src/music_collector/stats.py` — 資料分析（總覽、重疊、來源比較）
- `src/music_collector/web.py` — Streamlit Web 介面
- `src/music_collector/main.py` — 主流程與 CLI
- `tests/` — 87 項測試（pytest + respx mock）

### 擷取器技術細節

| 擷取器 | 方式 | 解析策略 |
|--------|------|----------|
| Pitchfork | HTML | `div[class*='SummaryItemWrapper']` 容器，`h3` 取曲名，`div sub-hed` 取藝人 |
| Stereogum | RSS | feedparser + 分類過濾 + 多格式標題解析 |
| NME | HTML | `/reviews/track` 頁面，敘述性標題解析（所有格 + 動詞短語分離） |
| SPIN | HTML | `/new-music/` 頁面，typographic 引號匹配 + 動詞短語分離 |
| Consequence | HTML | 引號提取曲名 + `_extract_artist_from_prefix()` 動詞邊界偵測 |
| Line of Best Fit | HTML | 所有格 `'s` 優先策略 + 擴展動詞清單 |
| Rolling Stone | HTML | 二階段：索引頁多頁掃描（≤3 頁）+ URL slug 匹配 → 文章頁提取曲目 |
| Slant | HTML | 引號提取 + Review 標題過濾 + JS/Cloudflare 偵測 |
| Complex | HTML | `/music` + `/tag/best-new-music` + JS 偵測 + Playwright fallback |
| Resident Advisor | HTML | Next.js 偵測 + Playwright fallback |
| Gorilla vs. Bear | RSS | feedparser + mp3/video/on-blast 分類過濾 |
| Bandcamp Daily | RSS | feedparser + Album of the Day 分類 + 逗號分隔解析 |
| The Quietus | RSS | feedparser + Reviews 分類過濾 |

### 引號處理注意事項

- Consequence：不可將直引號 `'` 放入引號匹配字元集，否則所有格會被誤判為開引號
- NME / SPIN：使用 `\u2019(?![a-zA-Z])` negative lookahead 避免將縮寫撇號（如 Where's）誤判為結尾引號
- SPIN：引號內曲名需 `rstrip(".,;:!?")` 移除尾端標點

## 新增擷取器

1. 在 `src/music_collector/scrapers/` 建立新檔案
2. 繼承 `BaseScraper`，實作 `fetch_tracks()` 回傳 `list[Track]`
3. 在 `scrapers/__init__.py` 的 `ALL_SCRAPERS` 中註冊
4. 在 `tests/scrapers/` 新增對應測試
5. 用 `--dry-run` 測試

## Apple Music（由 Soundiiz 外部同步）

> **重要**：專案內已無任何 Apple Music 程式碼。歷來嘗試過的三種做法皆已移除 ——
> TuneMyMusic Selenium 自動化、Apple Music REST API（Safari cookie token + `auth_server.py`）、
> macOS 音樂 App 手動 TXT 匯入。最後一種的根本缺陷是「匯入播放清單」只比對既有資料庫、
> 不查 Apple Music 目錄，冷門曲目結構性無法匹配。

### 現行架構

```
主歌單 Critics' Picks — Fresh Tracks（每季歸檔，只留當季）
   └─ mirror_to_all_time() 同步鏡射
Critics' Picks — All Time（只進不出，永不歸檔）
   └─ Soundiiz Auto-Sync（每週）
Apple Music 同名歌單
```

Soundiiz 只能盯單一歌單同步，而主歌單每季會被 `archive_previous_quarters()` 搬空，
因此另建 All Time 累積歌單作為同步來源，確保 Apple Music 那份保有完整歷史。

### 相關程式碼（皆在 `spotify.py`）

- `mirror_to_all_time(sp, uris)` — 去重後寫入 All Time 歌單，`run()` 每次加入新曲目後呼叫，包 try/except（失敗不影響主流程）
- `backfill_all_time(sp)` — 列舉主歌單 + 所有 `Critics' Picks —` 歸檔歌單（排除 All Time 自己）回填。因為底層去重，同時是一次性初始化與事後修復工具
- `config.ALL_TIME_PLAYLIST_NAME` — 可用環境變數 `ALL_TIME_PLAYLIST_NAME` 覆寫

### Soundiiz 設定（一次性手動）

1. `./run.sh --backfill-all-time` 建立並回填 All Time 歌單
2. `./run.sh --export-spotify-url` 取得歌單連結
3. Soundiiz Premium → Auto-Sync：source = Spotify `Critics' Picks — All Time`，
   destination = Apple Music 同名歌單，頻率每週

### 已知限制

- Soundiiz 的曲目比對仍可能漏掉極冷門曲目，但它查的是 Apple Music 目錄，涵蓋率遠高於音樂 App 的本地比對
- Auto-Sync 為單向（Spotify → Apple Music），在 Apple Music 端手動增刪不會回傳

## 自動排程（launchd）

### 排程設定

- 專案內：`com.music-collector.plist`（以 `run-scheduled.sh` 為入口）
- 安裝位置：`~/Library/LaunchAgents/com.music-collector.plist`
- 每週日 09:00 執行，log 輸出至 `data/collector.log`

**重要**：專案內的 plist 與安裝的 plist 必須保持一致。更新後須重新安裝：

```bash
cp com.music-collector.plist ~/Library/LaunchAgents/
launchctl unload ~/Library/LaunchAgents/com.music-collector.plist
launchctl load ~/Library/LaunchAgents/com.music-collector.plist
```

### 執行流程（`run-scheduled.sh`）

```bash
# 單一步驟：擷取 → Spotify → All Time 鏡射 → 備份 → 季度歸檔 → 通知
PYTHONPATH=src uv run python -m music_collector
```

Apple Music 不在排程範圍內 —— 由 Soundiiz 在雲端依自身排程從 Spotify 拉取。

### 排程指令

```bash
# 安裝排程
cp com.music-collector.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.music-collector.plist

# 移除排程
launchctl unload ~/Library/LaunchAgents/com.music-collector.plist

# 檢查狀態
launchctl list | grep music-collector

# 手動觸發（測試用）
launchctl start com.music-collector
```

## 注意事項

- `.env`、`.spotify_cache`、`data/` 不可推送至 Git
- 每個擷取器必須獨立處理例外，不可影響其他來源
- Spotify 搜尋先用精確查詢 `track: artist:`，失敗後再用寬鬆查詢，兩者皆需通過藝人 + 曲名雙重驗證
- 曲目去重以大小寫不敏感的 `(artist, title)` 比對
- 備份/通知/All Time 鏡射各自 try/except，失敗不影響主流程
- `--dry-run` 模式不觸發 Spotify 操作、備份與通知
- Spotify 認證失敗會被攔截並發送 `send_error_notification()`，不再靜默炸掉整個排程；
  修復方式為 `rm .spotify_cache` 後執行 `./run.sh` 重新完成瀏覽器授權
