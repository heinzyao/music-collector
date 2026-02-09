# 多 Agent 協作指引

本專案支援多個 AI Agent 協同開發，包含 Claude Code、OpenCode 及 Antigravity Agent。

## 協作架構

```
┌─────────────────────────────────────────────────┐
│                music-collector                   │
├──────────┬──────────────┬───────────────────────┤
│ Claude   │  OpenCode    │  Antigravity Agent    │
│ Code     │              │                       │
├──────────┼──────────────┼───────────────────────┤
│ 擷取器   │  擷取器開發  │  排程與部署自動化     │
│ 開發維護 │  資料品質分析 │  監控與告警           │
│ Spotify  │  新來源探索  │  跨平台整合           │
│ 整合     │  測試覆蓋    │  效能優化             │
└──────────┴──────────────┴───────────────────────┘
```

## 共享介面

### 資料模型

所有 Agent 操作曲目時，必須遵循統一的資料模型：

```python
@dataclass
class Track:
    artist: str   # 藝人名稱（去除前後空白）
    title: str    # 曲目名稱（去除前後空白）
    source: str   # 來源媒體名稱
```

### SQLite 資料庫

位置：`data/tracks.db`

```sql
CREATE TABLE tracks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    artist TEXT NOT NULL,
    title TEXT NOT NULL,
    source TEXT NOT NULL,
    spotify_uri TEXT,
    added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(artist, title)
);
```

- 去重以 `LOWER(artist)` + `LOWER(title)` 比對
- `spotify_uri` 為 NULL 代表在 Spotify 上未找到

### 擷取器介面

新增擷取器的標準步驟：

1. 在 `src/music_collector/scrapers/` 建立模組
2. 繼承 `BaseScraper`，設定 `name` 屬性
3. 實作 `fetch_tracks() -> list[Track]`
4. 在 `scrapers/__init__.py` 的 `ALL_SCRAPERS` 註冊

### 工具方法

`BaseScraper` 提供以下共用方法：

- `_get(url)` — HTTP GET，含 User-Agent 與逾時處理
- `_get_rendered(url, wait_selector)` — Playwright 瀏覽器渲染（需 ENABLE_PLAYWRIGHT=true）
- `parse_artist_title(text)` — 解析 "Artist – Title" 格式
- `clean_text(text)` — 清理空白與 HTML 實體

## 協作守則

### 一般規範

- 所有程式碼變更需保持向後相容
- 每個擷取器獨立模組，失敗不影響其他來源
- 不得將憑證（`.env`、`.spotify_cache`）推送至版本控制

### 分支策略

```
main          ← 穩定版本
├── feat/*    ← 新功能（新擷取器、新平台整合）
├── fix/*     ← 修復（擷取器適配、解析修正）
└── agent/*   ← Agent 自動化提交
```

### 可擴充方向

以下為預留的擴充空間，歡迎各 Agent 認領：

- [x] **新擷取器**：Gorilla vs. Bear、Bandcamp Daily、The Quietus
- [x] **解析品質**：改善 Consequence、Slant 的標題解析精確度
- [x] **擷取器重寫**：Pitchfork（RSS→HTML）、NME（新 URL + 敘述性標題解析器）、SPIN（新 URL + 敘述性標題解析器）
- [x] **JS 偵測**：Slant、Complex、Resident Advisor 加入 JS 渲染/Cloudflare 偵測
- [x] **JS 渲染來源**：整合 Playwright 處理 Complex、Resident Advisor（httpx → Playwright 自動 fallback）
- [x] **多平台輸出**：Spotify 播放清單 URL 匯出（供 TuneMyMusic/Soundiiz 轉換至 YouTube Music、Tidal 等）
- [x] **通知系統**：LINE + Telegram + Slack 多通道推送
- [x] **資料分析**：曲目趨勢、跨來源重疊分析、來源效能比較（--stats CLI）
- [x] **測試覆蓋**：82 項測試（pytest + respx mock），涵蓋 13 個擷取器
- [x] **容器化**：Dockerfile + docker-compose.yml + GitHub Actions CI/CD
- [x] **Web 介面**：Streamlit 瀏覽蒐集紀錄、來源統計、季度備份管理
