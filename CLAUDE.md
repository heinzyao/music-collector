# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 專案概述

自動從 13 個音樂評論網站蒐集推薦曲目，同步至 Spotify 與 Apple Music 播放清單。

## 開發指令

```bash
# 安裝依賴
uv sync

# 安裝含 Playwright 瀏覽器渲染
uv sync --extra browser

# 安裝含測試工具
uv sync --extra test

# 乾跑測試（不需 Spotify 憑證）
./run.sh --dry-run

# 完整執行（需 .env 中的 Spotify 憑證）
./run.sh

# 查看近期蒐集紀錄
./run.sh --recent 7

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
- `src/music_collector/spotify.py` — Spotify 整合（搜尋驗證、播放清單管理、季度歸檔）
- `src/music_collector/db.py` — SQLite 去重，以 `(artist, title)` 為唯一鍵
- `src/music_collector/backup.py` — 季度 JSON 備份至 `data/backups/YYYY/QN.json`
- `src/music_collector/export.py` — 匯出為 CSV/TXT；`export_combined_spotify()` 合併主歌單 + 歸檔歌單並去重匯出，供 Apple Music 使用
- `src/music_collector/apple_music/` — Apple Music 自動匯入（模組化套件）
  - `api.py` — **主要入口**：直接呼叫 Apple Music REST API（搜尋曲目、建立/刪除播放清單、分批加入曲目）
  - `browser.py` — Chrome driver 建立與反偵測措施，`create_driver()` 使用持久化 `data/browser_profile/`
  - `playlist.py` — 播放清單管理（MusicKit JS API + AppleScript fallback）
  - `transfer.py` — TuneMyMusic 自動化轉移（備援方案，不在日常排程中使用）
- `src/music_collector/tunemymusic.py` — 向後相容，重新匯出 `apple_music` 套件
- `src/music_collector/notify.py` — LINE + Telegram + Slack 多通道通知
- `src/music_collector/stats.py` — 資料分析（總覽、重疊、來源比較）
- `src/music_collector/web.py` — Streamlit Web 介面
- `src/music_collector/main.py` — 主流程與 CLI
- `tests/` — 90 項測試（pytest + respx mock）

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

## Apple Music 直接 API 匯入

### 流程架構（`api.py`）

```
讀取 data/apple_music_tokens.json
→ _validate_session()（輕量 API 驗證）
→ 逐一搜尋 (artist, title) → 取得 catalog track ID
→ 刪除同名舊歌單 → 建立新播放清單 → 分批 POST 加入曲目（每批 ≤300）
```

`api.py` 不含任何 Selenium 或瀏覽器自動化。所有 API 呼叫均為純 `httpx` REST 請求。

### Token 取得（`auth_server.py`）

`auth_server.py` 實作 Safari cookie 讀取授權（macOS 主路線）：

1. AppleScript 呼叫 Safari 對 `music.apple.com` 分頁執行 `document.cookie`
2. 正則擷取 `media-user-token` 值（即 `musicUserToken`）
3. 從 `music.apple.com` Vite JS bundle 提取 `developerToken`
4. 合併儲存至 `data/apple_music_tokens.json`

**前置條件（一次性）**：
- Safari → 偏好設定 → 進階 → 勾選「在選單列中顯示開發選單」
- Safari → 開發 → 勾選「允許 JavaScript 從 Apple 事件執行」
- 在 Safari 開啟 `music.apple.com` 並完成 Apple ID 登入

### Token 驗證

- `_load_token_file()`：讀取 token 檔，超過 `TOKEN_FILE_MAX_AGE_HOURS`（23 小時）視為過期
- `_validate_session()`：打 `GET /v1/me/library/playlists` 驗證（最多 2 次重試）
- Token 無效 → 拋出 `AppleMusicAuthRequiredError`，排程自動跳過並發 LINE 通知

### 非互動環境偵測

`_interactive_login_allowed()` 檢查三個 stdio stream 是否全為 TTY。排程環境（launchd 將 stdio 重導至 log 檔）回傳 False，立即拋出 `AppleMusicAuthRequiredError`，不阻塞排程。可用 `MUSIC_COLLECTOR_ALLOW_INTERACTIVE_APPLE_LOGIN=1` 覆寫。

### 已知限制

- Token（Safari cookie）有效期數週至數月，到期需重新執行 `./recover-apple-music-sync.sh`
- Apple Music API 每次 POST 最多加入 300 首，超過需分批
- `data/apple_music_tokens.json` 含敏感 token，不可推送至 Git

## Apple Music Session 恢復流程

Session 過期時，排程會自動跳過並發 LINE 通知。手動恢復步驟：

```bash
./recover-apple-music-sync.sh
```

流程：
1. `auth_server.py` 從 Apple Music bundle 取得 `developerToken`
2. 啟動 `localhost:8765` 授權頁面，自動開啟真實 Chrome
3. 使用者點擊「授權 Apple Music」→ 完成 Apple ID 登入（Email → 密碼 → 2FA）
4. Token 儲存至 `data/apple_music_tokens.json`
5. 自動執行完整同步（`./sync-apple-music.sh`）

## 自動排程（launchd）

### 排程設定

- 專案內：`com.music-collector.plist`（以 `run-scheduled.sh` 為入口）
- 安裝位置：`~/Library/LaunchAgents/com.music-collector.plist`
- 每日 09:00 執行，log 輸出至 `data/collector.log`

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
