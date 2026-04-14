# Music Collector

[English](#english) | [繁體中文](#繁體中文)

---

## English

Automatically collects "Best New Track" recommendations from major global music review websites and syncs them to Spotify and Apple Music.

### Feature Overview

The following workflow is executed automatically every day:

```text
13 Sources → Extract Tracks → Match with Spotify → Add to Playlist → Auto-export CSV → Apple Music API Direct Import → LINE Notification
```

#### Core Features

- **Spotify Search Validation**: Dual verification combining artist name and track title to ensure that the added song corresponds with the original source.
- **Apple Music Automatic Sync**: Directly calls the Apple Music REST API (MusicKit) to import playlists without relying on any third-party transfer service.
- **Quarterly Archiving**: Automatically moves expired tracks out of the main playlist into an archived playlist (`Critics' Picks — YYYY QN`) per quarter.
- **Browser State Retention**: Reuses the saved Apple ID browser session when available. If Apple Music requires re-authentication in a non-interactive environment, the sync is skipped immediately with a clear warning instead of blocking the schedule.
- **Multi-channel Notifications**: Sends execution summaries containing the sync results across the two major platforms via LINE, Telegram, and Slack.
- **Local Backup**: Retains quarterly backup copies of all track metadata under a `data/backups/YYYY/QN.json` structure.
- **Multi-platform Export**: Generates Spotify URLs capable of being imported into TuneMyMusic or Soundiiz to be mapped into YouTube Music, Tidal, etc.
- **Data Analysis**: Features source-contribution statistics, Spotify match rates, and cross-reference overlap analysis.
- **Web Interface**: A Streamlit environment to view historical logs, data distribution, and backup archives.
- **Playwright Support**: Provides seamless fallback to browser-rendering for Javascript-heavy scraping targets.

#### Supported Music Media Outlets

| Source | Format | Method | Status |
|--------|--------|--------|--------|
| Pitchfork | HTML | `/reviews/best/tracks/` Best track index | Stable |
| Stereogum | RSS | `stereogum.com/feed/` Filtered by singles category | Stable |
| The Line of Best Fit | HTML | Tracks parsed from `/tracks` path | Stable |
| Consequence | HTML | Filtered through Weekly Highlights | Stable |
| NME | HTML | Targeted by individual `/reviews/track` pages | Stable |
| SPIN | HTML | Parses the `/new-music/` directory | Stable |
| Rolling Stone | HTML | Combines index pages along with track features | Stable |
| Slant Magazine | HTML | `/music/` track review pages (includes JS verification) | Stable |
| Complex | HTML | Extracts from `/music` (requires Playwright fallback) | JS rendered |
| Resident Advisor | HTML | Queries `ra.co/reviews/singles` (requires Playwright fallback) | JS rendered |
| Gorilla vs. Bear | RSS | Retrieves `gorillavsbear.net/feed/` via mp3/video filtering | Stable |
| Bandcamp Daily | RSS | Uses `daily.bandcamp.com/feed` pointing to Album of the Day | Stable |
| The Quietus | RSS | Parses `thequietus.com/feed` via Reviews designation | Stable |

### Quick Start

#### Requirements

- Python 3.14+
- [uv](https://docs.astral.sh/uv/) Toolkit / Dependency Manager
- Spotify Developer Dashboard credentials ([Register Here](https://developer.spotify.com/dashboard))

#### Installation

```bash
git clone https://github.com/heinzyao/music-collector.git
cd music-collector
uv sync
```

#### Configuring Credentials

1. Clone `.env.example` as `.env`:

```bash
cp .env.example .env
```

2. **Spotify** (Mandatory): Setup an application at the [Spotify Developer Dashboard](https://developer.spotify.com/dashboard), note down the `SPOTIFY_CLIENT_ID` and `SPOTIFY_CLIENT_SECRET`. Configure `http://127.0.0.1:8888/callback` as a valid Redirect URI.

3. **Notifications** (Optional):
   - **LINE**: In the [LINE Developers Console](https://developers.line.biz/console/), register `LINE_CHANNEL_ID`, `LINE_CHANNEL_SECRET`, `LINE_USER_ID`.
   - **Telegram**: Initialize via [@BotFather](https://t.me/BotFather), enter `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`.
   - **Slack**: Setup an Incoming Webhook, copy the path into `SLACK_WEBHOOK_URL`.

4. Initial Spotify OAuth flow (A browser will be invoked to securely log in):

```bash
PYTHONPATH=src uv run python auth.py
```

#### Executing the script

```bash
# Complete flow (Parse + Spotify Upload + Backup + Notify)
./run.sh

# Dry mode (Parse elements WITHOUT saving to database or services)
./run.sh --dry-run

# Show recently scraped items for the past N days
./run.sh --recent 7

# Display all backup quarters
./run.sh --backup

# Fetch backup statistics for a specific quarter (E.g. Q1, 2026Q1, 2026/Q1)
./run.sh --backup Q1

# Multi-platform exports
./run.sh --export Q1              # standard CSV format
./run.sh --export Q1 --format txt # text format list
./run.sh --export Q1 --all        # include items ignored by Spotify
./run.sh --export-spotify-url     # output Spotify URLs for TuneMyMusic

# Full run + Apple Music sync (Scrape → Spotify → Apple Music)
./run.sh --import Q1

# Analysis Metrics
./run.sh --stats              # Overview
./run.sh --stats overlap      # Display duplicates across sites
./run.sh --stats sources      # Source ranking

# Web App
./run.sh --web

# Erase the timeline and the database to restart syncing
./run.sh --reset

# Manual Apple Music sync: use this when you're present to complete Apple login if needed
./run.sh --apple-music

# Recommended manual recovery shortcut for Apple Music re-auth / re-sync
./sync-apple-music.sh

# Bootstrap Apple login in a normal Chrome window first if session expired
./bootstrap-apple-music-login.sh

# Guided recovery: open normal Chrome login, verify the shared session, then continue to sync
./recover-apple-music-sync.sh

# Double-clickable bootstrap launcher for Finder / Desktop use
./bootstrap-apple-music-login.command

# Double-clickable guided recovery launcher
./recover-apple-music-sync.command

# Double-clickable launcher for Finder / Desktop use
./sync-apple-music.command
```

> Note: Using `run.sh` acts simply as a macro to `PYTHONPATH=src uv run python -m music_collector`.

### Spotify Playlist Control

#### Structure

| Playlist | Usage |
|----------|-------|
| **Critics' Picks — Fresh Tracks** | Primary target playlist consisting strictly of the new quarter |
| **Critics' Picks — 2026 Q1** | Indexed archive listing all songs from 2026, Quarter 1 |
| **Critics' Picks — 2025 Q4** | Indexed archive listing all songs from 2025, Quarter 4 |
| ... | Generates automatically in succession |

#### The Archiving Loop Process

A validation pass runs iteratively during script execution over the main playlist to identify stale artifacts:
1. Calculates track longevity strictly upon Spotify's recorded `added_at` stamp to observe its corresponding quarter framework.
2. An autonomous instance of a quarterly archiving playlist (E.g., `Critics' Picks — 2026 Q1`) targets expired metrics.
3. Obsolete entries transition into the allocated backlog and disappear from the `Fresh Tracks` sequence.
4. Active, timely selections continue mapping naturally in the active environment.

### Project Structure

```text
music-collector/
├── pyproject.toml                  # Settings & pip requirements
├── .env.example                    # Environment variable templates
├── run.sh                          # CLI manual execution macro
├── auth.py                         # Single-use Spotify OAuth authenticator
├── Dockerfile                      # Docker Build directives
├── docker-compose.yml              # Standardized services
├── com.music-collector.plist       # macOS OS-level launchd directive
├── .github/workflows/ci.yml       # GitHub Actions CI testing stack
├── src/
│   └── music_collector/
│       ├── __main__.py             # Base CLI runner root
│       ├── main.py                 # Core routing handling (Concurrent scraping)
│       ├── config.py               # Constants mapping to ENV files
│       ├── spotify.py              # Extends spotipy
│       ├── db.py                   # Deduplication and local SQLite persistence
│       ├── backup.py               # Produces the JSON quarter log logic
│       ├── export.py               # Serializes the outputs to CSV/TXT/Spotify URL vectors
│       ├── notify.py               # Dispatching hooks utilizing Webhooks
│       ├── stats.py                # Mathematical overlapping evaluation
│       ├── web.py                  # Local frontend driven by Streamlit
│       ├── apple_music/            # Integrates directly to Apple Music
│       │   ├── __init__.py
│       │   ├── api.py              # Direct Apple Music REST API import (primary)
│       │   ├── browser.py          # Chrome Driver handler & Anti-bot stealth logic
│       │   ├── playlist.py         # Extends AppleScript & MusicKit to create logic
│       │   └── transfer.py         # TuneMyMusic GUI automation (legacy fallback)
│       ├── tunemymusic.py          # Bridging backward compatibility logic
│       └── scrapers/
│           ├── __init__.py         # Global Scraper Repository Array (13 Modules)
│           ├── base.py             # Skeleton implementation logic extending beautifulsoup + Playwright
│           ├── pitchfork.py        # Pitchfork (HTML)
│           ├── stereogum.py        # Stereogum (RSS)
│           ├── lineofbestfit.py    # The Line of Best Fit
│           ├── consequence.py      # Consequence of Sound
│           ├── nme.py              # NME
│           ├── spin.py             # SPIN
│           ├── rollingstone.py     # Rolling Stone
│           ├── slant.py            # Slant Magazine
│           ├── complex.py          # Complex (+ Playwright)
│           ├── residentadvisor.py  # Resident Advisor (+ Playwright)
│           ├── gorillavsbear.py    # Gorilla vs. Bear (RSS)
│           ├── bandcamp.py         # Bandcamp Daily (RSS)
│           └── quietus.py          # The Quietus (RSS)
├── tests/
│   ├── conftest.py                 # PyTest standard fixtures
│   ├── fixtures/html/              # Embedded sample testing mock HTML models
│   └── scrapers/                   # Individual unittests verifying array outputs
└── data/
    ├── tracks.db                   # Main memory cache SQLite DB
    ├── collector.log               # CLI activity tracing log stream
    ├── browser_profile/            # User-Data Chrome profiles matching Selenium logins (Apple ID persistence)
    ├── backups/                    # Target log dump folder
    └── exports/                    # External output container
```

### Docker Deployments

```bash
# Prepare image
docker compose build

# Command trigger
docker compose run collector

# Dry trigger
docker compose run collector --dry-run

# Run Analytics Engine
docker compose run collector --stats
```

### Daily Automation

#### macOS launchd (Preferred Methodology)

```bash
cp com.music-collector.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.music-collector.plist
```

This binds an automatic timer executing around 09:00 locally every day. This trigger is bound implicitly to the XML `<dict> StartCalendarInterval` value in the file itself.

The scheduled LaunchAgent intentionally runs the **crawler + Spotify pipeline only**. Apple Music sync remains a manual command because Apple may require an interactive sign-in at any time. If `--apple-music` is run from a non-interactive environment and the saved Apple session is no longer valid, the program now skips Apple Music sync immediately with a clear warning instead of waiting for the login timeout.

When that happens, first use `./bootstrap-apple-music-login.sh` to sign in through a normal Chrome window with the shared browser profile, then run `./sync-apple-music.sh` to reuse that session for the automated sync.

Additional manual recovery tools:
- `./recover-apple-music-sync.command`: guided recovery launcher with pre-sync session validation
- `./bootstrap-apple-music-login.command`: double-clickable login bootstrap launcher
- `./sync-apple-music.command`: double-clickable Finder launcher
- `com.music-collector.apple-music-manual.plist`: optional per-user LaunchAgent you can start manually with `launchctl start com.music-collector.apple-music-manual`

#### crontab Option

```bash
0 9 * * * cd /path/to/music-collector && PYTHONPATH=src uv run python -m music_collector >> data/collector.log 2>&1
```

### Tech Stack / Selection Justification

| Architecture | System | Methodology / Rationale |
|--------------|--------|-------------------------|
| Ecosystem Tooling | uv | Extremely fast lockfile handling |
| Network Transport | httpx | Inherently asynchronous processing patterns |
| Document Tracing | BeautifulSoup + lxml | Dependable DOM tree traversal mechanisms |
| Document Tracing | feedparser | De Facto RSS compliance parser |
| Rendering Engine | Playwright (Available On-Demand) | Executes Chrome instances implicitly via headless React interception |
| Audio API Layer | Spotify (via spotipy) | Streamlines Bearer logic inside automation intervals |
| DB Layering | SQLite | High capability logic with 0 dependencies required to execute |
| Signaling Layer | httpx (API endpoint logic) | Bridges LINE / Telegram without additional SDK bloatware required |
| Interface Layer | Streamlit (On-Demand) | Connects intuitively directly to sqlite for fast GUI interactions |
| Remote CI Pipeline | GitHub Actions | Configured automatically via ruff and pytest compliance standards Python 3.14+ |
| Sandboxing Model | Docker | Extends a python:3.14-slim instance + uv preinstalled environment |

### Contributions & Enhancements

#### Writing additional modules

Append any logic structure directly utilizing the `BaseScraper` class:

```python
from .base import BaseScraper, Track

class NewSourceScraper(BaseScraper):
    name = "New Source"

    def fetch_tracks(self) -> list[Track]:
        # Custom logic implementation bounds here
        return [Track(artist="...", title="...", source=self.name)]
```

Add your scraper directly inside the `scrapers/__init__.py` under the `ALL_SCRAPERS` list array.

#### Multi-Agent Synergy

- **CLAUDE.md** — Preconfigured Claude system behavioral file mapping prompts appropriately
- **AGENTS.md** — Interaction schema logic documenting workflows directly implemented within the Antigravity scope
- Code segments run autonomously per scraper object; breaking errors inherently bounce back independently without terminating system instances.
- SQLite remains as the fundamental local context registry tracking global dependencies.

### License

MIT License

---

## 繁體中文

自動從全球主要音樂評論網站蒐集「最佳新曲」推薦，並同步至 Spotify 與 Apple Music。

### 功能概覽

每日自動執行以下流程：

```text
13 個來源 → 擷取曲目 → Spotify 比對 → 加入歌單 → 自動匯出 CSV → Apple Music API 直接匯入 → LINE 通知
```

#### 核心功能

- **Spotify 搜尋驗證**：藝人名稱 + 曲目名稱雙重比對，確保加入的歌曲與來源一致
- **Apple Music 自動同步**：直接呼叫 Apple Music REST API（MusicKit），不依賴任何第三方轉換服務，將歌單直接匯入 Apple Music
- **季度歸檔**：每季自動將過季曲目從主播放清單移至 `Critics' Picks — YYYY QN` 歸檔清單
- **瀏覽器狀態保存**：會重用已儲存的 Apple ID 瀏覽器 session；若 Apple Music 在非互動環境中要求重新登入，程式會立即略過同步並記錄明確警告，不再卡住整個排程
- **多通道通知**：LINE + Telegram + Slack 推送執行摘要，包含兩大平台同步結果
- **本地備份**：以 `data/backups/YYYY/QN.json` 季度結構備份所有曲目紀錄
- **多平台匯出**：Spotify URL 匯出，供 TuneMyMusic/Soundiiz 轉換至 YouTube Music、Tidal 等
- **資料分析**：來源貢獻、Spotify 配對率、跨來源重疊分析
- **Web 介面**：Streamlit 瀏覽蒐集紀錄、來源統計、季度備份管理
- **Playwright 支援**：JS 重度渲染網站自動 fallback 至瀏覽器渲染

#### 支援的音樂媒體來源

| 來源 | 類型 | 擷取方式 | 狀態 |
|------|------|----------|------|
| Pitchfork | HTML | `/reviews/best/tracks/` 最佳曲目頁面 | 穩定 |
| Stereogum | RSS | `stereogum.com/feed/` 過濾單曲相關分類 | 穩定 |
| The Line of Best Fit | HTML | `/tracks` 頁面，解析每日推薦 | 穩定 |
| Consequence | HTML | WordPress 分類頁，週度精選 | 穩定 |
| NME | HTML | `/reviews/track` 個別曲目評論頁 | 穩定 |
| SPIN | HTML | `/new-music/` 分類頁面 | 穩定 |
| Rolling Stone | HTML | 音樂新聞與特輯索引頁 + 文章頁 | 穩定 |
| Slant Magazine | HTML | `/music/` 樂評頁（含 JS 偵測） | 穩定 |
| Complex | HTML | `/music` 等（含 JS 偵測 + Playwright fallback） | JS 渲染 |
| Resident Advisor | HTML | `ra.co/reviews/singles`（含 Playwright fallback） | JS 渲染 |
| Gorilla vs. Bear | RSS | `gorillavsbear.net/feed/` 過濾 mp3/video 分類 | 穩定 |
| Bandcamp Daily | RSS | `daily.bandcamp.com/feed` Album of the Day | 穩定 |
| The Quietus | RSS | `thequietus.com/feed` 過濾 Reviews 分類 | 穩定 |

### 快速開始

#### 前置需求

- Python 3.14+
- [uv](https://docs.astral.sh/uv/) 套件管理工具
- Spotify 開發者帳號（[申請](https://developer.spotify.com/dashboard)）

#### 安裝

```bash
git clone https://github.com/heinzyao/music-collector.git
cd music-collector
uv sync
```

#### 設定憑證

1. 複製 `.env.example` 為 `.env`：

```bash
cp .env.example .env
```

2. **Spotify**（必要）：前往 [Spotify Developer Dashboard](https://developer.spotify.com/dashboard)，建立應用程式並填入 `SPOTIFY_CLIENT_ID` 和 `SPOTIFY_CLIENT_SECRET`。設定 Redirect URI 為 `http://127.0.0.1:8888/callback`。

3. **通知**（選用）：
   - **LINE**：前往 [LINE Developers Console](https://developers.line.biz/console/)，填入 `LINE_CHANNEL_ID`、`LINE_CHANNEL_SECRET`、`LINE_USER_ID`
   - **Telegram**：建立 Bot（[@BotFather](https://t.me/BotFather)），填入 `TELEGRAM_BOT_TOKEN`、`TELEGRAM_CHAT_ID`
   - **Slack**：建立 Incoming Webhook，填入 `SLACK_WEBHOOK_URL`

4. 首次 Spotify 授權（開啟瀏覽器進行 OAuth 認證）：

```bash
PYTHONPATH=src uv run python auth.py
```

#### 使用方式

```bash
# 完整執行（擷取 + Spotify + 備份 + 通知）
./run.sh

# 僅擷取，不寫入 Spotify / 不備份 / 不通知（測試用）
./run.sh --dry-run

# 查看最近 N 天蒐集的曲目
./run.sh --recent 7

# 列出所有備份檔案
./run.sh --backup

# 檢視指定季度備份內容（支援 Q1、2026Q1、2026/Q1 等格式）
./run.sh --backup Q1

# 匯出備份供多平台匯入
./run.sh --export Q1              # CSV 格式
./run.sh --export Q1 --format txt # 純文字格式
./run.sh --export Q1 --all        # 包含 Spotify 未找到的曲目
./run.sh --export-spotify-url     # 輸出 Spotify 連結供轉換

# 完整執行 + Apple Music 同步（擷取 → Spotify → Apple Music）
./run.sh --import Q1

# 資料分析
./run.sh --stats              # 總覽
./run.sh --stats overlap      # 跨來源重疊
./run.sh --stats sources      # 來源比較

# Web 介面
./run.sh --web

# 清除歌單與資料庫，重新蒐集
./run.sh --reset

# 手動 Apple Music 同步：當你人在電腦前、可視需要完成 Apple 登入時使用
./run.sh --apple-music

# 建議的 Apple Music 補跑捷徑：重新授權或手動重試時使用
./sync-apple-music.sh

# 若 session 過期，先用一般 Chrome 視窗完成 Apple 登入
./bootstrap-apple-music-login.sh

# 引導式兩段恢復：先登入，驗證 session 後再按 Enter 接續同步
./recover-apple-music-sync.sh

# 可雙擊的登入初始化啟動器
./bootstrap-apple-music-login.command

# 可雙擊的引導式恢復啟動器
./recover-apple-music-sync.command

# 可雙擊的 Finder / Desktop 啟動器
./sync-apple-music.command
```

> `run.sh` 等同 `PYTHONPATH=src uv run python -m music_collector`，可直接傳遞所有參數。

### Spotify 播放清單管理

#### 播放清單結構

| 播放清單 | 用途 |
|----------|------|
| **Critics' Picks — Fresh Tracks** | 主清單，僅包含當季新曲目 |
| **Critics' Picks — 2026 Q1** | 歸檔清單，2026 年第 1 季的曲目 |
| **Critics' Picks — 2025 Q4** | 歸檔清單，2025 年第 4 季的曲目 |
| ... | 依此類推，自動建立 |

#### 季度歸檔機制

每次執行時自動檢查主播放清單中是否有「前季」曲目：
1. 依據 Spotify `added_at` 時間判斷曲目所屬季度
2. 自動建立季度歸檔播放清單（如 `Critics' Picks — 2026 Q1`）
3. 將過季曲目移入歸檔清單，從主清單移除
4. 當季曲目留在主清單中

### 專案結構

```text
music-collector/
├── pyproject.toml                  # 專案設定與依賴
├── .env.example                    # 環境變數範本
├── run.sh                          # 手動執行腳本
├── auth.py                         # Spotify OAuth 一次性授權工具
├── Dockerfile                      # Docker 容器化
├── docker-compose.yml              # Docker Compose 設定
├── com.music-collector.plist       # macOS launchd 排程設定
├── .github/workflows/ci.yml       # GitHub Actions CI
├── src/
│   └── music_collector/
│       ├── __main__.py             # CLI 進入點
│       ├── main.py                 # 主流程調度器（並行擷取）
│       ├── config.py               # 環境變數與常數
│       ├── spotify.py              # Spotify API 整合
│       ├── db.py                   # SQLite 曲目紀錄與去重
│       ├── backup.py               # 季度 JSON 備份
│       ├── export.py               # CSV/TXT/Spotify URL 匯出
│       ├── notify.py               # LINE + Telegram + Slack 通知
│       ├── stats.py                # 資料分析模組
│       ├── web.py                  # Streamlit Web 介面
│       ├── apple_music/            # Apple Music 自動匯入（模組化）
│       │   ├── __init__.py
│       │   ├── api.py              # Apple Music REST API 直接匯入（主要）
│       │   ├── browser.py          # Chrome driver 與反偵測
│       │   ├── playlist.py         # 播放清單管理（MusicKit JS + AppleScript）
│       │   └── transfer.py         # TuneMyMusic 自動化轉移（備援）
│       ├── tunemymusic.py          # 向後相容（重新匯出 apple_music）
│       └── scrapers/
│           ├── __init__.py         # 擷取器註冊表（13 個）
│           ├── base.py             # 基礎擷取器（含 Playwright）
│           ├── pitchfork.py        # Pitchfork (HTML)
│           ├── stereogum.py        # Stereogum (RSS)
│           ├── lineofbestfit.py    # The Line of Best Fit
│           ├── consequence.py      # Consequence of Sound
│           ├── nme.py              # NME
│           ├── spin.py             # SPIN
│           ├── rollingstone.py     # Rolling Stone
│           ├── slant.py            # Slant Magazine
│           ├── complex.py          # Complex (+ Playwright)
│           ├── residentadvisor.py  # Resident Advisor (+ Playwright)
│           ├── gorillavsbear.py    # Gorilla vs. Bear (RSS)
│           ├── bandcamp.py         # Bandcamp Daily (RSS)
│           └── quietus.py          # The Quietus (RSS)
├── tests/
│   ├── conftest.py                 # 全域 fixtures
│   ├── fixtures/html/              # HTML fixture 檔案
│   └── scrapers/                   # 擷取器測試（13 個）
└── data/
    ├── tracks.db                   # SQLite 資料庫
    ├── collector.log               # 排程執行日誌
    ├── browser_profile/            # Selenium Chrome 使用者資料（Apple ID 登入狀態）
    ├── backups/                    # 季度 JSON 備份
    └── exports/                    # 匯出檔案
```

### Docker 部署

```bash
# 建置映像
docker compose build

# 執行完整蒐集
docker compose run collector

# 乾跑模式
docker compose run collector --dry-run

# 資料分析
docker compose run collector --stats
```

### 每日自動排程

#### macOS launchd（建議）

```bash
cp com.music-collector.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.music-collector.plist
```

預設每日 09:00 執行。編輯 plist 中的 `StartCalendarInterval` 可調整時間。

目前 LaunchAgent 刻意只執行 **爬蟲 + Spotify 流程**，不會自動觸發 Apple Music 同步。原因是 Apple 可能隨時要求互動式重新登入；若在非互動環境中執行 `--apple-music` 且既有 session 已失效，程式現在會立即略過 Apple Music 同步並輸出明確警告，而不是等待登入逾時。

若遇到這種情況，請先在終端執行 `./bootstrap-apple-music-login.sh`，用一般 Chrome 視窗完成 Apple 登入；登入完成後再執行 `./sync-apple-music.sh` 補跑同步。

另外也提供兩個手動補跑入口：
- `./recover-apple-music-sync.command`：雙擊後會先開正常 Chrome 讓你登入，先驗證 session 可用，再接續同步
- `./bootstrap-apple-music-login.command`：可從 Finder 直接雙擊，先開正常 Chrome 登入 Apple
- `./sync-apple-music.command`：可從 Finder 直接雙擊執行
- `com.music-collector.apple-music-manual.plist`：可安裝成使用者 LaunchAgent，並用 `launchctl start com.music-collector.apple-music-manual` 手動觸發

#### crontab 替代方案

```bash
0 9 * * * cd /path/to/music-collector && PYTHONPATH=src uv run python -m music_collector >> data/collector.log 2>&1
```

### 技術選型

| 元件 | 選擇 | 原因 |
|------|------|------|
| 套件管理 | uv | 速度快、Lockfile 支援 |
| HTTP 請求 | httpx | 現代化、支援非同步 |
| HTML 解析 | BeautifulSoup + lxml | 穩定、容錯佳 |
| RSS 解析 | feedparser | 業界標準 |
| JS 渲染 | Playwright（選用） | headless Chrome，處理 React/Next.js |
| 音樂串流 | Spotify (spotipy) | Token 可自動更新，適合排程 |
| 資料儲存 | SQLite | 零依賴、去重可靠 |
| 推播通知 | httpx 直接呼叫 API | LINE + Telegram + Slack，免額外套件 |
| Web 介面 | Streamlit（選用） | 零配置、直接讀取 SQLite |
| CI/CD | GitHub Actions | Python 3.14 + uv + ruff + pytest |
| 容器化 | Docker | python:3.14-slim + uv |

### 擴充與協作

#### 新增擷取器

繼承 `BaseScraper` 即可新增來源：

```python
from .base import BaseScraper, Track

class NewSourceScraper(BaseScraper):
    name = "New Source"

    def fetch_tracks(self) -> list[Track]:
        # 實作擷取邏輯
        return [Track(artist="...", title="...", source=self.name)]
```

並在 `scrapers/__init__.py` 的 `ALL_SCRAPERS` 中註冊。

#### Agent 協作

- **CLAUDE.md** — Claude Code 專案指引
- **AGENTS.md** — 多 Agent 協作規範（OpenCode、Antigravity Agent）
- 每個擷取器獨立模組，失敗不影響其他來源
- SQLite 資料庫提供共享狀態

### 授權條款

MIT License
