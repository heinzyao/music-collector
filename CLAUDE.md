# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 專案概述

自動從 13 個音樂評論網站蒐集推薦曲目，同步至 Spotify 與 Apple Music 播放清單。

## 開發指令

```bash
# 安裝依賴（含 Playwright，Resident Advisor 需要）
uv sync --extra browser

# 安裝 Playwright Chromium 瀏覽器（首次安裝後僅需執行一次）
uv run playwright install chromium

# 安裝含測試工具
uv sync --extra test

# 乾跑測試（不需 Spotify 憑證）
./run.sh --dry-run

# 完整執行（需 .env 中的 Spotify 憑證）
./run.sh

# 查看近期蒐集紀錄
./run.sh --recent 7

# 合併匯出 Apple Music 手動匯入檔（主歌單 + 所有歸檔歌單去重，產出單一 TXT）
# 註：自動刪除舊歌單的邏輯已停用，此指令現與 --apple-music 產出相同的手動匯入檔
./run.sh --merge-apple-music

# 執行測試（全部）
PYTHONPATH=src uv run pytest tests/ -q

# 執行單一測試檔案
PYTHONPATH=src uv run pytest tests/test_apple_music_api.py -v

# 執行單一測試
PYTHONPATH=src uv run pytest tests/test_apple_music_api.py::test_validate_session_retries -v

# Apple Music 同步（手動，互動環境）
./sync-apple-music.sh

# Apple Music Session 恢復（首次登入或 session 過期）
./recover-apple-music-sync.sh
```

> `run.sh` 等同 `PYTHONPATH=src uv run python -m music_collector`。

## 架構要點

- `src/music_collector/scrapers/base.py` — `BaseScraper` 抽象類別、`Track` 資料模型、`_get_rendered()` Playwright 方法
- `src/music_collector/scrapers/__init__.py` — `ALL_SCRAPERS` 註冊表（13 個擷取器）
- `src/music_collector/health.py` — `record_scrape_result()`、`get_unhealthy_sources()`、`get_health_report()`
- `src/music_collector/spotify.py` — Spotify 整合（搜尋驗證、播放清單管理、季度歸檔）
- `src/music_collector/db.py` — SQLite 去重，以 `(artist, title)` 為唯一鍵
- `src/music_collector/backup.py` — 季度 JSON 備份至 `data/backups/YYYY/QN.json`
- `src/music_collector/export.py` — 匯出為 CSV/TXT；`export_combined_spotify()` 合併主歌單 + 歸檔歌單並去重匯出，供 Apple Music 使用
- `src/music_collector/apple_music/` — Apple Music 匯入（手動 TXT 匯出）
  - `api.py` — **唯一模組**：`import_to_apple_music()` 由 CSV 產出 Tab 分隔的手動匯入 TXT 並印出匯入指引。其餘 `_load_token_file()`、`_validate_session()`、`list_playlists_by_prefix()`、`AppleMusicAuthRequiredError` 等為保留相容性的 no-op stub
- `src/music_collector/notify.py` — LINE + Telegram + Slack 多通道通知
- `src/music_collector/stats.py` — 資料分析（總覽、重疊、來源比較）
- `src/music_collector/web.py` — Streamlit Web 介面
- `src/music_collector/main.py` — 主流程與 CLI
- `tests/` — 88 項測試（pytest + respx mock）

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

## Apple Music 匯入（手動 TXT 匯出）

> **重要**：先前的 Apple Music REST API 自動同步（Safari cookie token、`auth_server.py`、瀏覽器自動化）已移除。現行機制改為產出可手動匯入的文字檔，不再需要 token 或 Safari 設定。`api.py` 中殘留的 `_load_token_file()`、`_validate_session()`、`list_playlists_by_*()`、`_delete_*()`、`AppleMusicAuthRequiredError` 皆為保留相容性的 no-op stub（恆回傳成功／空值，不會拋出）。

### 流程架構（`api.py`）

```
export_combined_spotify() 合併主歌單 + 所有歸檔歌單並去重
→ 產出 data/exports/<歌單名>.csv 與 <歌單名>_Apple_Music.txt（Tab 分隔）
→ import_to_apple_music() 確保 TXT 已生成，並在終端印出手動匯入指引
```

`api.py` 不含任何 API 呼叫、Selenium、token 或瀏覽器自動化。

### 手動匯入步驟

1. 執行 `./sync-apple-music.sh`（或排程的 `--apple-music`）產出 `data/exports/<歌單名>_Apple_Music.txt`
2. macOS「音樂 (Music)」App →「檔案」→「資料庫」→「匯入播放清單...」
3. 選取該 TXT，Music App 自動比對曲庫並建立同名播放清單

### 已知限制

- Music App 依曲名／藝人字串比對，個別冷門曲目可能匹配失敗
- `data/`（含匯出檔）不推送至 Git

## Apple Music Session 恢復流程

已無 session／token 概念。`./recover-apple-music-sync.sh` 現僅提示改用手動匯出模式，並可直接轉呼 `./sync-apple-music.sh` 產出匯入檔。

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
# Step 1：擷取 → Spotify → 備份 → 通知
PYTHONPATH=src uv run python -m music_collector

# Step 2：Apple Music 同步（session 有效時靜默執行，過期時發通知跳過）
PYTHONPATH=src uv run python -m music_collector --apple-music || true
```

排程使用兩段式：Spotify 先完成後才進行 Apple Music，確保 Apple Music 匯出包含最新曲目。Apple Music 失敗不影響整體排程（`|| true`）。

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
- 備份/通知各自 try/except，失敗不影響主流程
- `--dry-run` 模式不觸發 Spotify 操作、備份與通知
