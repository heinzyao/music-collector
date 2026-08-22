# Music Collector

[English](#english) | [繁體中文](#繁體中文)

---

## English

Automatically collects "Best New Track" recommendations from major global music review websites and syncs them to a Spotify playlist. Spotify is the only target platform.

### Feature Overview

The following workflow is executed automatically every week:

```text
13 Sources → Extract Tracks → Match with Spotify → Add to Playlist → Mirror to All Time Playlist → LINE Notification
```

#### Core Features

- **Spotify Search Validation**: Dual verification combining artist name and track title to ensure that the added song corresponds with the original source.
- **Quarterly Archiving**: Automatically moves expired tracks out of the main playlist into an archived playlist (`Critics' Picks — YYYY QN`) per quarter.
- **All Time Cumulative Playlist**: Every matched track is also mirrored into `Critics' Picks — All Time`, an append-only playlist that is never archived — the single place to see everything ever collected, since the main playlist rolls over each quarter.
- **Multi-channel Notifications**: Sends execution summaries via LINE, Telegram, and Slack — including an alert when Spotify authorization expires, instead of failing the schedule silently.
- **Local Backup**: Retains quarterly backup copies of all track metadata under a `data/backups/YYYY/QN.json` structure.
- **Export**: Quarterly backups to CSV/TXT, plus Spotify playlist URLs and track counts.
- **Data Analysis**: Features source-contribution statistics, Spotify match rates, and cross-reference overlap analysis.
- **Web Interface**: A Streamlit environment to view historical logs, data distribution, and backup archives.
- **Playwright Support**: Provides seamless fallback to browser-rendering for Javascript-heavy scraping targets.
- **Source Health Monitoring**: Automatically detects sources that are failing consecutively or returning zero tracks for multiple days, and sends alerts via LINE/Telegram/Slack.

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
| DIY | RSS | News category, artist from tags, single name from quotes | Stable |
| Aquarium Drunkard | RSS | ` :: ` separator, column blacklist, artist must match a tag | Stable |

### Quick Start

#### Requirements

- Python 3.14+
- [uv](https://docs.astral.sh/uv/)
- Spotify Developer Dashboard credentials ([Register Here](https://developer.spotify.com/dashboard))

#### Installation

```bash
git clone https://github.com/heinzyao/music-collector.git
cd music-collector
uv sync
```

#### Configuring Credentials

1. Copy `.env.example` to `.env`:

```bash
cp .env.example .env
```

2. **Spotify** (Mandatory): Setup an application at the [Spotify Developer Dashboard](https://developer.spotify.com/dashboard), note down the `SPOTIFY_CLIENT_ID` and `SPOTIFY_CLIENT_SECRET`. Configure `http://127.0.0.1:8888/callback` as a valid Redirect URI.

3. **Notifications** (Optional):
   - **LINE**: In the [LINE Developers Console](https://developers.line.biz/console/), register `LINE_CHANNEL_ID`, `LINE_CHANNEL_SECRET`, `LINE_USER_ID`.
   - **Telegram**: Initialize via [@BotFather](https://t.me/BotFather), enter `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`.
   - **Slack**: Setup an Incoming Webhook, copy the path into `SLACK_WEBHOOK_URL`.

4. **Source Health Thresholds** (Optional):
   - `SOURCE_FAILURE_THRESHOLD`: Consecutive failures before marking a source as unhealthy (default: 3).
   - `SOURCE_EMPTY_DAYS_THRESHOLD`: Consecutive days with zero tracks before warning (default: 5).

5. Run the one-time Spotify OAuth flow (a browser window will open for login):

```bash
PYTHONPATH=src uv run python auth.py
```

#### Usage

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
./run.sh --export-spotify-url     # output Spotify playlist URLs and track counts

# Backfill the All Time cumulative playlist (main + every quarterly archive, deduped)
./run.sh --backfill-all-time

# Analysis Metrics
./run.sh --stats              # Overview
./run.sh --stats overlap      # Display duplicates across sites
./run.sh --stats sources      # Source ranking

# Source Health Report
./run.sh --health             # Show health status of all scrapers

# Web App
./run.sh --web

# Erase the timeline and the database to restart syncing
./run.sh --reset
```

> Note: Using `run.sh` acts simply as a macro to `PYTHONPATH=src uv run python -m music_collector`.

### Spotify Playlist Control

#### Structure

| Playlist | Usage |
|----------|-------|
| **Critics' Picks — Fresh Tracks** | Primary target playlist consisting strictly of the new quarter |
| **Critics' Picks — All Time** | Append-only cumulative playlist, never archived. Everything ever collected, in one place |
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
├── .python-version                 # Python version pin
├── CLAUDE.md                       # Claude Code project guide
├── AGENTS.md                       # Multi-agent collaboration guide
├── auth.py                         # Single-use Spotify OAuth authenticator
├── Dockerfile                      # Docker build directives
├── docker-compose.yml              # Docker Compose services
│
│   # ─── Shell scripts ───
├── run.sh                          # CLI manual execution macro
├── run-scheduled.sh                # Daily schedule wrapper (crawl → Spotify → notify)
├── clean.sh                        # Disk cleanup utility
│
│   # ─── macOS launchd template ───
├── com.music-collector.plist.example
│
│   # ─── GitHub Actions ───
├── .github/workflows/ci.yml       # CI: ruff lint + pytest
│
├── src/
│   └── music_collector/
│       ├── __main__.py             # CLI entry point
│       ├── main.py                 # Core router (concurrent scraping)
│       ├── config.py               # Environment variables & constants
│       ├── spotify.py              # Spotify API integration (spotipy)
│       ├── db.py                   # SQLite deduplication & persistence
│       ├── backup.py               # Quarterly JSON backup
│       ├── export.py               # CSV / TXT / Spotify URL export
│       ├── notify.py               # LINE + Telegram + Slack notifications
│       ├── stats.py                # Source contribution & overlap analytics
│       ├── web.py                  # Streamlit web interface
│       ├── clean.py                # Cache / log / export cleanup
│       └── scrapers/
│           ├── __init__.py         # Scraper registry (13 modules)
│           ├── base.py             # BaseScraper + Track model + Playwright support
│           ├── pitchfork.py        # Pitchfork (HTML)
│           ├── stereogum.py        # Stereogum (RSS)
│           ├── lineofbestfit.py    # The Line of Best Fit (HTML)
│           ├── consequence.py      # Consequence of Sound (HTML)
│           ├── nme.py              # NME (HTML)
│           ├── spin.py             # SPIN (HTML)
│           ├── rollingstone.py     # Rolling Stone (HTML)
│           ├── slant.py            # Slant Magazine (HTML + JS detection)
│           ├── complex.py          # Complex (HTML + Playwright)
│           ├── residentadvisor.py  # Resident Advisor (HTML + Playwright)
│           ├── gorillavsbear.py    # Gorilla vs. Bear (RSS)
│           ├── bandcamp.py         # Bandcamp Daily (RSS)
│           └── quietus.py          # The Quietus (RSS)
├── tests/
│   ├── conftest.py                 # Global pytest fixtures
│   ├── test_spotify.py             # Spotify search & All Time playlist tests
│   ├── test_notify.py              # Notification tests
│   ├── fixtures/html/              # HTML mock fixtures
│   └── scrapers/                   # Per-scraper unit tests (13 modules)
└── data/                           # Local runtime data (git-ignored)
    ├── tracks.db                   # SQLite database
    ├── collector.log               # Scheduled run log
    ├── backups/                    # Quarterly JSON backups
    └── exports/                    # Export output files
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

The scheduled LaunchAgent runs a single step: crawl → Spotify → All Time mirror → backup → quarterly archive → notification. If Spotify authorization has expired, the run stops early and sends an alert telling you to re-authorize (`rm .spotify_cache && ./run.sh`).

#### Why there is no Apple Music support

Four approaches were tried and all removed: TuneMyMusic Selenium automation, the Apple Music REST API via a scraped Safari cookie token, manual TXT import into the macOS Music app (which only matches your existing library, never the Apple Music catalog), and Soundiiz Auto-Sync. The official MusicKit API requires a paid Apple Developer membership, and at 1500+ tracks the playlist exceeds every free transfer service's quota. Spotify is the only target platform.

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

自動從全球主要音樂評論網站蒐集「最佳新曲」推薦，並同步至 Spotify 播放清單。Spotify 是唯一目標平台。

### 功能概覽

每天自動執行以下流程：

```text
15 個來源 → 擷取曲目 → Spotify 比對 → 加入歌單 → 鏡射至 All Time 累積歌單 → LINE 通知
```

#### 核心功能

- **Spotify 搜尋驗證**：藝人名稱 + 曲目名稱雙重比對，確保加入的歌曲與來源一致
- **季度歸檔**：每季自動將過季曲目從主播放清單移至 `Critics' Picks — YYYY QN` 歸檔清單
- **All Time 累積歌單**：所有配對成功的曲目同時鏡射至只進不出、永不歸檔的 `Critics' Picks — All Time`。主歌單每季輪替、歷史散落在各季歸檔中，這份是唯一能一眼看完所有蒐集結果的歌單
- **多通道通知**：LINE + Telegram + Slack 推送執行摘要；Spotify 授權失效時也會發送警示，不再靜默失敗
- **本地備份**：以 `data/backups/YYYY/QN.json` 季度結構備份所有曲目紀錄
- **匯出**：季度備份匯出為 CSV／TXT，並可輸出 Spotify 歌單連結與曲目數
- **資料分析**：來源貢獻、Spotify 配對率、跨來源重疊分析
- **Web 介面**：Streamlit 瀏覽蒐集紀錄、來源統計、季度備份管理
- **Playwright 支援**：JS 重度渲染網站自動 fallback 至瀏覽器渲染
- **來源健康監控**：自動偵測連續失敗或長期無曲目的來源，透過 LINE/Telegram/Slack 發送警示

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
| DIY | RSS | News 分類，tag 取藝人、引號取曲名 | 穩定 |
| Aquarium Drunkard | RSS | ` :: ` 分隔，專欄黑名單 + tag 驗證 | 穩定 |

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

4. **來源健康檢查閾值**（選用）：
   - `SOURCE_FAILURE_THRESHOLD`：連續失敗幾次標記為 unhealthy（預設：3）
   - `SOURCE_EMPTY_DAYS_THRESHOLD`：連續幾天無曲目發出警告（預設：5）

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
./run.sh --export-spotify-url     # 輸出 Spotify 歌單連結與曲目數

# 回填 All Time 累積歌單（主歌單 + 所有季度歸檔，去重）
./run.sh --backfill-all-time

# 資料分析
./run.sh --stats              # 總覽
./run.sh --stats overlap      # 跨來源重疊
./run.sh --stats sources      # 來源比較

# 來源健康狀態
./run.sh --health             # 顯示各擷取器健康狀態

# Web 介面
./run.sh --web

# 清除歌單與資料庫，重新蒐集
./run.sh --reset
```

> `run.sh` 等同 `PYTHONPATH=src uv run python -m music_collector`，可直接傳遞所有參數。

### Spotify 播放清單管理

#### 播放清單結構

| 播放清單 | 用途 |
|----------|------|
| **Critics' Picks — Fresh Tracks** | 主清單，僅包含當季新曲目 |
| **Critics' Picks — All Time** | 累積清單，只進不出、永不歸檔，歷來蒐集的全部曲目 |
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
├── .python-version                 # Python 版本鎖定
├── CLAUDE.md                       # Claude Code 專案指引
├── AGENTS.md                       # 多 Agent 協作規範
├── auth.py                         # Spotify OAuth 一次性授權工具
├── Dockerfile                      # Docker 容器化
├── docker-compose.yml              # Docker Compose 設定
│
│   # ─── Shell 腳本 ───
├── run.sh                          # 手動執行腳本
├── run-scheduled.sh                # 每日排程腳本（擷取 → Spotify → 通知）
├── clean.sh                        # 磁碟空間清理工具
│
│   # ─── macOS launchd 範本 ───
├── com.music-collector.plist.example
│
│   # ─── GitHub Actions ───
├── .github/workflows/ci.yml       # CI：ruff lint + pytest
│
├── src/
│   └── music_collector/
│       ├── __main__.py             # CLI 進入點
│       ├── main.py                 # 主流程調度器（並行擷取）
│       ├── config.py               # 環境變數與常數
│       ├── spotify.py              # Spotify API 整合
│       ├── db.py                   # SQLite 曲目紀錄與去重
│       ├── backup.py               # 季度 JSON 備份
│       ├── export.py               # CSV / TXT / Spotify URL 匯出
│       ├── notify.py               # LINE + Telegram + Slack 通知
│       ├── stats.py                # 資料分析模組
│       ├── web.py                  # Streamlit Web 介面
│       ├── clean.py                # 快取／日誌／匯出清理
│       └── scrapers/
│           ├── __init__.py         # 擷取器註冊表（15 個）
│           ├── base.py             # 基礎擷取器（含 Playwright）
│           ├── pitchfork.py        # Pitchfork (HTML)
│           ├── stereogum.py        # Stereogum (RSS)
│           ├── lineofbestfit.py    # The Line of Best Fit (HTML)
│           ├── consequence.py      # Consequence of Sound (HTML)
│           ├── nme.py              # NME (HTML)
│           ├── spin.py             # SPIN (HTML)
│           ├── rollingstone.py     # Rolling Stone (HTML)
│           ├── slant.py            # Slant Magazine (HTML + JS 偵測)
│           ├── complex.py          # Complex (HTML + Playwright)
│           ├── residentadvisor.py  # Resident Advisor (HTML + Playwright)
│           ├── gorillavsbear.py    # Gorilla vs. Bear (RSS)
│           ├── bandcamp.py         # Bandcamp Daily (RSS)
│           └── quietus.py          # The Quietus (RSS)
├── tests/
│   ├── conftest.py                 # 全域 fixtures
│   ├── test_spotify.py             # Spotify 搜尋與 All Time 歌單測試
│   ├── test_notify.py              # 通知模組測試
│   ├── fixtures/html/              # HTML fixture 檔案
│   └── scrapers/                   # 擷取器測試（15 個）
└── data/                           # 本地執行資料（git-ignored）
    ├── tracks.db                   # SQLite 資料庫
    ├── collector.log               # 排程執行日誌
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

預設每天 09:00 執行。編輯 plist 中的 `StartCalendarInterval` 可調整時間。

LaunchAgent 執行單一步驟：擷取 → Spotify → All Time 鏡射 → 備份 → 季度歸檔 → 通知。若 Spotify 授權已失效，執行會提早結束並發送警示，提醒你重新授權（`rm .spotify_cache && ./run.sh`）。

#### 為什麼不支援 Apple Music

四種做法都試過並全數移除：TuneMyMusic Selenium 自動化、以刮取的 Safari cookie token 呼叫 Apple Music REST API、macOS 音樂 App 手動 TXT 匯入（只比對既有資料庫、不查 Apple Music 目錄）、Soundiiz Auto-Sync。官方 MusicKit API 需付費 Apple Developer 會員；而歌單已達 1500+ 首，超出所有免費轉換服務的額度。Spotify 是唯一目標平台。

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
