# Music Collector

自動從全球主要音樂評論網站蒐集「最佳新曲」推薦，並建立 Spotify 播放清單。

## 功能概覽

每日自動執行以下流程：

```
10 個音樂媒體來源 → 擷取推薦曲目 → 去重 → Spotify 搜尋比對 → 加入播放清單 → 季度歸檔 → 本地備份 → LINE 通知
```

### 核心功能

- **Spotify 搜尋驗證**：藝人名稱 + 曲目名稱雙重比對，確保加入的歌曲與來源一致
- **季度歸檔**：每季自動將過季曲目從主播放清單移至 `Critics' Picks — YYYY QN` 歸檔清單
- **本地備份**：以 `data/backups/YYYY/QN.json` 季度結構備份所有曲目紀錄
- **LINE 通知**：每次執行完成後透過 LINE Messaging API 推送摘要（選用）

### 支援的音樂媒體來源

| 來源 | 類型 | 擷取方式 | 標題格式範例 | 狀態 |
|------|------|----------|-------------|------|
| Pitchfork | HTML | `/reviews/best/tracks/` 最佳曲目頁面 | `SummaryItemWrapper` 元件解析 | 穩定（30 首） |
| Stereogum | RSS | `stereogum.com/feed/` 過濾單曲相關分類 | `Artist – "Song"`, `Artist Shares New Song "Title"` | 穩定 |
| The Line of Best Fit | HTML | `/tracks` 頁面，解析每日推薦 | `ARTIST drops euphoric new track 'Song'` | 穩定 |
| Consequence | HTML | WordPress 分類頁，週度精選 | `Song of the Week: Artist's "Song" Description` | 穩定 |
| NME | HTML | `/reviews/track` 個別曲目評論頁 | `Artist's new single 'Title' review` | 穩定 |
| SPIN | HTML | `/new-music/` 分類頁面 | `Artist Explore Darkness on 'Song'` | 穩定 |
| Rolling Stone | HTML | `/music/music-news/` 與 `/music/music-features/` 從近期文章提取曲目 | `Artist Shares New Song 'Title'` | 穩定 |
| Slant Magazine | HTML | `/music/` 樂評頁，從評論標題提取（含 JS 偵測） | `Artist 'Album' Review: Description` | 穩定 |
| Complex | HTML | 嘗試 `/music`、`/tag/best-new-music`（含 JS 偵測） | `Artist "Song"` | JS 渲染，受限 |
| Resident Advisor | HTML | `ra.co/reviews/singles`（含 JS 偵測） | `Artist – Title` | JS 渲染，受限 |

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

3. **LINE 通知**（選用）：前往 [LINE Developers Console](https://developers.line.biz/console/)，建立 Messaging API Channel，填入 `LINE_CHANNEL_ID`、`LINE_CHANNEL_SECRET` 和 `LINE_USER_ID`。未設定時自動跳過。

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
├── run.sh                          # 手動執行腳本（支援所有 CLI 參數）
├── auth.py                         # Spotify OAuth 一次性授權工具
├── com.music-collector.plist       # macOS launchd 排程設定
├── src/
│   └── music_collector/
│       ├── __main__.py             # CLI 進入點
│       ├── main.py                 # 主流程調度器
│       ├── config.py               # 環境變數與常數
│       ├── spotify.py              # Spotify API 整合（搜尋驗證、季度歸檔）
│       ├── db.py                   # SQLite 曲目紀錄與去重
│       ├── backup.py               # 季度 JSON 備份
│       ├── notify.py               # LINE Messaging API 通知
│       └── scrapers/
│           ├── __init__.py         # 擷取器註冊表
│           ├── base.py             # 基礎擷取器抽象類別
│           ├── pitchfork.py        # Pitchfork (HTML)
│           ├── stereogum.py        # Stereogum (RSS)
│           ├── lineofbestfit.py    # The Line of Best Fit
│           ├── consequence.py      # Consequence of Sound
│           ├── nme.py              # NME
│           ├── spin.py             # SPIN
│           ├── rollingstone.py     # Rolling Stone
│           ├── slant.py            # Slant Magazine
│           ├── complex.py          # Complex
│           └── residentadvisor.py  # Resident Advisor
└── data/
    ├── tracks.db                   # SQLite 資料庫（自動建立）
    ├── collector.log               # 排程執行日誌
    └── backups/                    # 季度 JSON 備份（自動建立）
        └── YYYY/QN.json
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
| 音樂串流 | Spotify (spotipy) | Token 可自動更新，適合排程 |
| 資料儲存 | SQLite | 零依賴、去重可靠 |
| 推播通知 | LINE Messaging API (httpx) | 免額外套件、Token 自動產生 |

> **為何不選 Apple Music？** Apple Music API 的 Token 無法自動更新（每次過期需手動重新授權），不適合無人值守的排程任務。

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
