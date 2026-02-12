# Music Collector

自動從全球主要音樂評論網站蒐集「最佳新曲」推薦，並同步至 Spotify 與 Apple Music。

## 功能概覽

每日自動執行以下流程：

```
13 個來源 → 擷取曲目 → Spotify 比對 → 加入歌單 → 自動匯出 CSV → TuneMyMusic 自動化 → Apple Music 同步 → LINE 通知
```

### 核心功能

- **Spotify 搜尋驗證**：藝人名稱 + 曲目名稱雙重比對，確保加入的歌曲與來源一致
- **Apple Music 自動同步**：透過 Selenium 自動化 TuneMyMusic 流程，將新歌單無縫接軌至 Apple Music
- **季度歸檔**：每季自動將過季曲目從主播放清單移至 `Critics' Picks — YYYY QN` 歸檔清單
- **瀏覽器狀態保存**：自動記憶 Apple ID 登入狀態，除首次授權外，後續可全自動執行
- **多通道通知**：LINE + Telegram + Slack 推送執行摘要，包含兩大平台同步結果
- **本地備份**：以 `data/backups/YYYY/QN.json` 季度結構備份所有曲目紀錄
- **多平台匯出**：Spotify URL 匯出，供 TuneMyMusic/Soundiiz 轉換至 YouTube Music、Tidal 等
- **資料分析**：來源貢獻、Spotify 配對率、跨來源重疊分析
- **Web 介面**：Streamlit 瀏覽蒐集紀錄、來源統計、季度備份管理
- **Playwright 支援**：JS 重度渲染網站自動 fallback 至瀏覽器渲染

### 支援的音樂媒體來源

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

## 快速開始

### 前置需求

- Python 3.14+
- [uv](https://docs.astral.sh/uv/) 套件管理工具
- Spotify 開發者帳號（[申請](https://developer.spotify.com/dashboard)）

### 安裝

```bash
git clone https://github.com/heinzyao/music-collector.git
cd music-collector
uv sync
```

### 設定憑證

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

### 使用方式

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
./run.sh --export-spotify-url     # 輸出 Spotify 連結供轉換

# 資料分析
./run.sh --stats              # 總覽
./run.sh --stats overlap      # 跨來源重疊
./run.sh --stats sources      # 來源比較

# Web 介面
./run.sh --web

# 清除歌單與資料庫，重新蒐集
./run.sh --reset
```

> `run.sh` 等同 `PYTHONPATH=src uv run python -m music_collector`，可直接傳遞所有參數。

## Spotify 播放清單管理

### 播放清單結構

| 播放清單 | 用途 |
|----------|------|
| **Critics' Picks — Fresh Tracks** | 主清單，僅包含當季新曲目 |
| **Critics' Picks — 2026 Q1** | 歸檔清單，2026 年第 1 季的曲目 |
| **Critics' Picks — 2025 Q4** | 歸檔清單，2025 年第 4 季的曲目 |
| ... | 依此類推，自動建立 |

### 季度歸檔機制

每次執行時自動檢查主播放清單中是否有「前季」曲目：
1. 依據 Spotify `added_at` 時間判斷曲目所屬季度
2. 自動建立季度歸檔播放清單（如 `Critics' Picks — 2026 Q1`）
3. 將過季曲目移入歸檔清單，從主清單移除
4. 當季曲目留在主清單中

## 專案結構

```
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
│       ├── main.py                 # 主流程調度器
│       ├── config.py               # 環境變數與常數
│       ├── spotify.py              # Spotify API 整合
│       ├── db.py                   # SQLite 曲目紀錄與去重
│       ├── backup.py               # 季度 JSON 備份
│       ├── export.py               # CSV/TXT/Spotify URL 匯出
│       ├── notify.py               # LINE + Telegram + Slack 通知
│       ├── stats.py                # 資料分析模組
│       ├── web.py                  # Streamlit Web 介面
│       ├── tunemymusic.py          # Apple Music 自動匯入
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

## Docker 部署

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

## 每日自動排程

### macOS launchd（建議）

```bash
cp com.music-collector.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.music-collector.plist
```

預設每日 09:00 執行。編輯 plist 中的 `StartCalendarInterval` 可調整時間。

### crontab 替代方案

```bash
0 9 * * * cd /path/to/music-collector && PYTHONPATH=src uv run python -m music_collector >> data/collector.log 2>&1
```

## 技術選型

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

## 擴充與協作

### 新增擷取器

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

### Agent 協作

- **CLAUDE.md** — Claude Code 專案指引
- **AGENTS.md** — 多 Agent 協作規範（OpenCode、Antigravity Agent）
- 每個擷取器獨立模組，失敗不影響其他來源
- SQLite 資料庫提供共享狀態

## 授權條款

MIT License
