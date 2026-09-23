# 多 Agent 協作指引

本檔定義跨 agent 共用的資料模型與擷取器介面；專案細節見 `CLAUDE.md`。

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
