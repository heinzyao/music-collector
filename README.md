# Music Collector

自動從全球主要音樂評論網站蒐集「最佳新曲」推薦，並建立 Spotify 播放清單。

## 功能概覽

每日自動執行以下流程：

```
10 個音樂媒體來源 → 擷取推薦曲目 → 去重 → Spotify 搜尋比對 → 加入播放清單
```

### 支援的音樂媒體來源

| 來源 | 擷取方式 | 狀態 |
|------|----------|------|
| Stereogum | RSS | 穩定運作 |
| The Line of Best Fit | HTML | 穩定運作 |
| Consequence | HTML | 穩定運作 |
| SPIN | HTML | 穩定運作 |
| Slant Magazine | HTML | 穩定運作 |
| Pitchfork | RSS | 需要 "Best New Track" 標籤 |
| NME | HTML | 需頁面結構適配 |
| Rolling Stone | HTML | 依季度清單而定 |
| Complex | HTML | JS 渲染，受限 |
| Resident Advisor | HTML | JS 渲染，受限 |

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

### 設定 Spotify 憑證

1. 前往 [Spotify Developer Dashboard](https://developer.spotify.com/dashboard) 建立應用程式
2. 設定 Redirect URI 為 `http://127.0.0.1:8888/callback`
3. 複製 `.env.example` 為 `.env` 並填入憑證：

```bash
cp .env.example .env
# 編輯 .env，填入 SPOTIFY_CLIENT_ID 和 SPOTIFY_CLIENT_SECRET
```

4. 首次授權（開啟瀏覽器進行 OAuth 認證）：

```bash
PYTHONPATH=src uv run python auth.py
```

### 使用方式

```bash
# 完整執行（擷取 + 加入 Spotify 播放清單）
PYTHONPATH=src uv run python -m music_collector

# 僅擷取，不寫入 Spotify（測試用）
PYTHONPATH=src uv run python -m music_collector --dry-run

# 查看最近 N 天蒐集的曲目
PYTHONPATH=src uv run python -m music_collector --recent 7
```

## 專案結構

```
music-collector/
├── pyproject.toml                  # 專案設定與依賴
├── .env.example                    # 環境變數範本
├── auth.py                         # Spotify OAuth 一次性授權工具
├── com.music-collector.plist       # macOS launchd 排程設定
├── src/
│   └── music_collector/
│       ├── __main__.py             # CLI 進入點
│       ├── main.py                 # 主流程調度器
│       ├── config.py               # 環境變數與常數
│       ├── spotify.py              # Spotify API 整合
│       ├── db.py                   # SQLite 曲目紀錄與去重
│       └── scrapers/
│           ├── __init__.py         # 擷取器註冊表
│           ├── base.py             # 基礎擷取器抽象類別
│           ├── pitchfork.py        # Pitchfork (RSS)
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
    └── tracks.db                   # SQLite 資料庫（自動建立）
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

> **為何不選 Apple Music？** Apple Music API 的 Token 無法自動更新（每次過期需手動重新授權），不適合無人值守的排程任務。

## 擴充與協作

本專案預留以下協作介面：

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
