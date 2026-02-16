# Music Collector — 專案指引

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

# 安裝含 Web 介面
uv sync --extra web

# 安裝所有可選依賴
uv sync --all-extras

# 乾跑測試（不需 Spotify 憑證）
./run.sh --dry-run

# 完整執行（需 .env 中的 Spotify 憑證）
./run.sh

# 查看近期蒐集紀錄
./run.sh --recent 7

# 檢視備份（列出所有 / 指定季度）
./run.sh --backup
./run.sh --backup Q1

# 匯出備份供 Apple Music 匯入
./run.sh --export Q1              # 匯出為 CSV（適用 TuneMyMusic）
./run.sh --export Q1 --format txt # 匯出為純文字
./run.sh --export Q1 --all        # 包含未在 Spotify 找到的曲目

# 輸出 Spotify 播放清單連結（供轉換至 YouTube Music / Tidal）
./run.sh --export-spotify-url

# 自動匯入 Apple Music（開啟瀏覽器，需手動登入 Apple ID）
./run.sh --import Q1

# 資料分析
./run.sh --stats              # 總覽
./run.sh --stats overlap      # 跨來源重疊分析
./run.sh --stats sources      # 各來源效能比較

# Web 介面
./run.sh --web

# 清除歌單與資料庫，重新蒐集
./run.sh --reset

# 執行測試
PYTHONPATH=src uv run pytest tests/ -v

# Docker 執行
docker compose run collector --dry-run
```

> `run.sh` 等同 `PYTHONPATH=src uv run python -m music_collector`。

## 架構要點

- `src/music_collector/scrapers/base.py` — `BaseScraper` 抽象類別、`Track` 資料模型、`_get_rendered()` Playwright 方法
- `src/music_collector/scrapers/__init__.py` — `ALL_SCRAPERS` 註冊表（13 個擷取器）
- `src/music_collector/spotify.py` — Spotify 整合（搜尋驗證、播放清單管理、季度歸檔）
- `src/music_collector/db.py` — SQLite 去重，以 `(artist, title)` 為唯一鍵
- `src/music_collector/backup.py` — 季度 JSON 備份至 `data/backups/YYYY/QN.json`
- `src/music_collector/export.py` — 匯出為 CSV/TXT（`export_from_spotify()` 直接從 Spotify API 讀取官方元資料；舊函式 `export_csv()`/`export_playlist()` 從備份 JSON 讀取）+ Spotify URL 匯出
- `src/music_collector/tunemymusic.py` — Selenium 自動化 TuneMyMusic 匯入 Apple Music
- `src/music_collector/notify.py` — LINE + Telegram + Slack 多通道通知
- `src/music_collector/stats.py` — 資料分析（總覽、重疊、來源比較）
- `src/music_collector/web.py` — Streamlit Web 介面
- `src/music_collector/main.py` — 主流程與 CLI
- `tests/` — 82 項測試（pytest + respx mock）

### 擷取器技術細節

| 擷取器 | 方式 | 解析策略 |
|--------|------|----------|
| Pitchfork | HTML | `div[class*='SummaryItemWrapper']` 容器，`h3` 取曲名，`div sub-hed` 取藝人 |
| Stereogum | RSS | feedparser + 分類過濾 + 多格式標題解析 |
| NME | HTML | `/reviews/track` 頁面，敘述性標題解析（所有格 + 動詞短語分離） |
| SPIN | HTML | `/new-music/` 頁面，typographic 引號匹配 + 動詞短語分離 |
| Consequence | HTML | 引號提取曲名 + `_extract_artist_from_prefix()` 動詞邊界偵測 |
| Line of Best Fit | HTML | 所有格 `'s` 優先策略 + 擴展動詞清單 |
| Rolling Stone | HTML | 二階段：索引頁篩選推薦文章 → 文章頁提取曲目 |
| Slant | HTML | 引號提取 + JS/Cloudflare 偵測 |
| Complex | HTML | 多 URL 嘗試 + JS 偵測 + Playwright fallback |
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

## Playwright 瀏覽器渲染

用於 JS 重度渲染網站（Complex、Resident Advisor）：

1. 安裝：`uv sync --extra browser && uv run playwright install chromium`
2. 啟用：在 `.env` 設定 `ENABLE_PLAYWRIGHT=true`
3. 行為：httpx 請求失敗時自動 fallback 至 Playwright headless 瀏覽器
4. 未安裝/未啟用時靜默跳過，不影響其他來源

## TuneMyMusic Apple Music 自動匯入

### 流程架構

```
匯出 CSV → Selenium 開啟 TuneMyMusic → 關閉 Cookie 同意 → 上傳 CSV → 欄位對應
→ 選擇歌單 → 設定播放清單名稱 → 選擇 Apple Music → 連接
→ Apple ID 彈窗授權 → 刪除同名舊播放清單 → 開始轉移 → 完成
→ MusicKit JS API 改名播放清單（確保名稱與 Spotify 同步）
```

所有步驟在同一 URL (`/transfer`) 上以 SPA 方式切換，共 4 個步驟（STEP 1/4 ~ 4/4）。

### Selector 策略

TuneMyMusic 使用 Next.js + CSS Modules，class name 為 hash（如 `MusicServiceBlock-module-scss-module__7DOuaW__Block`），每次建置都會變更。因此：

- **使用 `name` 屬性**（穩定、不受語系與 CSS 模組影響）：
  - `button[name='FromFile']` — 選擇上傳來源
  - `button[name='Apple']` — 選擇 Apple Music 目標
  - `button[name='stickyButton']` — Continue / Choose Destination（各步驟共用）
- **避免 CSS class selector** — 所有 class 皆為 CSS module hash
- **XPath fallback** 限定為 `//button[...]` 而非 `//*[...]`，避免匹配無關元素

### Apple ID 授權流程

1. 點擊 Connect → MusicKit JS 發起 OAuth
2. 瀏覽器開啟新視窗至 `idmsa.apple.com` 供使用者登入
3. 使用者完成登入 → 彈窗自動關閉
4. 主頁面收到授權 token → 進入轉移步驟

程式碼透過 `window_handles` 偵測彈窗、等待關閉、切回主視窗。

### 播放清單名稱與去重

- **名稱設定（雙重保障）**：
  - **UI 層**（best-effort）：`_set_playlist_name()` 在「Choose Destination」步驟前嘗試找到可編輯欄位修改名稱，但 TuneMyMusic UI 經常變動，可能失敗
  - **API 層**（可靠）：`_rename_apple_music_playlist()` 在轉移完成後透過 MusicKit JS API（`PATCH /v1/me/library/playlists/{id}`）將播放清單改名為 `PLAYLIST_NAME`，搜尋候選名稱 "My Playkist"（TuneMyMusic 預設）或 CSV 檔名
- **去重策略**：TuneMyMusic 每次轉移必定建立新播放清單，`_delete_existing_apple_music_playlist()` 在授權完成後、開始轉移前，透過 MusicKit JS API（`/v1/me/library/playlists`）找到同名舊播放清單並刪除，確保只有一個播放清單
- `import_to_apple_music()` 接受 `playlist_name` 參數，由 `main.py` 傳入 `PLAYLIST_NAME`

### 反偵測措施

MusicKit JS 會偵測無痕模式（透過 IndexedDB quota、Service Worker、storage API）。`_create_driver()` 中的防護：

- `Page.addScriptToEvaluateOnNewDocument` 注入反偵測腳本（每個頁面載入都生效）
- `navigator.storage.estimate` quota 偽裝（無痕模式 < 120MB → 偽裝為 4GB）
- 第三方 cookie 允許（Apple OAuth 需要）
- 持久化 `user-data-dir` 保存登入狀態

### 已知限制

- 首次使用需手動在 Apple ID 彈窗完成登入（約 30 秒）
- 後續執行若 session 仍有效則可全自動
- `data/browser_profile/` 儲存 Chrome profile（不可推送至 Git）

## 自動排程（launchd）

### 設定檔

- 專案內：`com.music-collector.plist`
- 安裝位置：`~/Library/LaunchAgents/com.music-collector.plist`
- 每日 09:00 執行，log 輸出至 `data/collector.log`

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

### 執行流程（`run(sync_apple_music=True)`）

排程使用 `--apple-music` 旗標，執行順序嚴格保證 **Spotify 先完成，再進行 Apple Music**：

```
1. 擷取新曲目（13 個來源）
2. Spotify 更新（僅有新曲目時）：搜尋 → 加入歌單 → 備份
3. Apple Music 匯入（無論是否有新曲目都執行）：從 Spotify API 匯出 CSV（官方元資料） → TuneMyMusic 轉移
4. 發送通知
```

Apple Music 匯入與新曲目解耦，確保即使當天無新曲目，前次失敗的匯入仍會重試。

## 注意事項

- `.env`、`.spotify_cache`、`data/` 不可推送至 Git
- 每個擷取器必須獨立處理例外，不可影響其他來源
- Spotify 搜尋先用精確查詢 `track: artist:`，失敗後再用寬鬆查詢，兩者皆需通過藝人 + 曲名雙重驗證
- 曲目去重以大小寫不敏感的 `(artist, title)` 比對
- 備份/通知各自 try/except，失敗不影響主流程
- `--dry-run` 模式不觸發 Spotify 操作、備份與通知
