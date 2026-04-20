# Apple Music Token 取得替代方案

**建立日期**：2026-04-20  
**完成日期**：2026-04-21  
**狀態**：✅ 方案 A 已實作並驗證通過（sync 成功執行）

**背景**：原有三條路線（Selenium、localhost HTTP server、osascript 注入 JS）全數失敗，需完全重新規劃。

---

## 最終解法摘要（2026-04-21）

**方案 A（Safari cookie）+ Origin header 修復**，兩個獨立問題的組合修復：

1. **token 取得**：`run_safari_cookie_auth()` 透過 AppleScript 讀 Safari `media-user-token` cookie，完全繞開 `MusicKit.authorize()`。
2. **API 呼叫**：所有 REST 請求加入 `Origin: https://music.apple.com` header。AMPWebPlay JWT（從 Vite bundle 提取）被 Apple API 綁定到此 origin，缺少時一律 401。

**關鍵發現**：先前所有 API 呼叫失敗（包含 token 看似有效的情況）的根本原因是 Origin header 缺失，而非 token 本身無效。

---

---

## 失敗根因總結

所有失敗都指向同一根源：試圖讓程式觸發 `MusicKit.authorize()`。

| 已失敗方案 | 失敗原因 |
|-----------|---------|
| Selenium Chrome | Apple 偵測 WebDriver bot，`MusicKit.authorize()` 回傳 "Authorization failed" |
| localhost HTTP 授權頁 | developerToken origin 限制，`authorize()` 只允許在 `music.apple.com` domain 呼叫，localhost 回傳 undefined |
| osascript 注入 JS 至真實 Chrome | AppleScript 字串跳脫 bug + MusicKit instance 不可靠，6 次重試仍回傳空字串 |

**新策略**：讓使用者正常登入，程式只負責撈取 Apple 自動產生的 cookie token。`api.py` REST 層完全不需變動。

---

## 技術前提

- `musicUserToken` = cookie `media-user-token`（Apple Music web 登入後自動設置）
- `developerToken` = Vite bundle JWT（現有 `fetch_developer_token()` 已正常運作）
- Token 有效後，`api.py` 純 REST 流程 94 項測試全數通過，不需變動

---

## 方案 A：Safari + AppleScript 讀 `media-user-token` cookie（首選）

### 核心機制

使用者在 Safari 登入 `music.apple.com` 後，Apple 自動將 `musicUserToken` 存入 cookie `media-user-token`。Python 以 AppleScript 呼叫 Safari 執行 `document.cookie`，正則擷取該值。**完全不觸碰 MusicKit JS**。

### 前置條件（一次性，兩個設定缺一不可）

1. Safari → 偏好設定 → 進階 → 勾選「在選單列中顯示「開發」選單」
2. Safari 選單列 → 開發 → 勾選「允許 JavaScript 從 Apple 事件執行」
   （注意：與「允許 Apple Events 進行遠端自動化」是不同選項，兩者都需啟用）

### 實作步驟

- [x] 完成上述兩個前置設定
- [x] 在 Safari 開 `music.apple.com` 完成 Apple ID 登入（勾選「保持登入」）
- [x] 新增 `auth_server.py` 函式 `run_safari_cookie_auth()`：
  - AppleScript `do JavaScript "document.cookie"` in Safari 對 `music.apple.com` 分頁
  - 從 cookie 字串擷取 `media-user-token=<value>`
  - `developerToken` 沿用現有 `fetch_developer_token()`（Vite bundle JWT）
  - 寫入 `data/apple_music_tokens.json`（格式不變）
- [x] 更新 `__main__` 入口：macOS 優先走 `run_safari_cookie_auth()`
- [x] 更新 `recover-apple-music-sync.sh` 文字說明
- [x] 更新 `CLAUDE.md` 授權流程段落

**追加修復**：
- [x] `api.py` `_make_headers()` 加入 `Origin: https://music.apple.com`（根本原因修復）
- [x] `search_track()` 加入 429 重試退避邏輯
- [x] `TOKEN_FILE_MAX_AGE_HOURS` 從 23 延長至 168（7 天）

### 把握度：高

AppleScript `do JavaScript` 讀 cookie 不依賴 MusicKit runtime，失敗面向完全不同於舊方案。Cookie 壽命遠長於 23 小時（通常數週至數月）。

### 風險與限制

- 需確認兩個 Safari 設定都已啟用（否則 AppleScript 回傳空字串，症狀與舊 Chrome 失敗相似）
- 若 Apple 將 `media-user-token` 改為 HttpOnly（目前 JS 可讀），需改走方案 C
- Cookie 到期需使用者重新登入 Safari（見「Token 過期恢復流程」）

### 最小驗證（30 秒，零開發成本）

確認兩個 Safari 設定啟用後，在 Safari DevTools Console 執行：
```js
document.cookie.split('; ').find(c => c.startsWith('media-user-token='))
```
- **有值** → 方案 A 直接可行，進入實作
- **undefined** → cookie 可能是 HttpOnly，改走方案 C

### Token 過期恢復流程

Cookie 過期時，排程自動略過並發 LINE 通知。恢復步驟：
1. 手動開 Safari，確認 `music.apple.com` 已登入（若已登出則重新登入）
2. 執行 `./recover-apple-music-sync.sh`
3. 腳本呼叫 `run_safari_cookie_auth()`，自動讀取 cookie 並寫入 token 檔
4. 接續執行 `sync-apple-music.sh` 完成同步

---

## 方案 C：Chrome CDP `Network.getCookies` 讀 cookie（方案 A 的 fallback）

### 核心機制

Chrome 以 `--remote-debugging-port=9222` 啟動（不加 `--enable-automation`，無 bot 偵測）。Python 透過 WebSocket 連接 CDP，使用 `Network.getCookies` 讀取 `music.apple.com` 所有 cookie，**包括 HttpOnly cookie**——這是優於方案 A 的關鍵點。

### 實作步驟

- [ ] `uv add websocket-client`（或 `pychrome`）
- [ ] 以 `data/auth_profile`（現有隔離 profile）+ `--remote-debugging-port=9222` 啟動 Chrome
- [ ] 使用者在 Chrome 完成 `music.apple.com` 登入（profile 持久化 cookie）
- [ ] Python 連接 `http://localhost:9222/json`，找 `music.apple.com` 分頁，建立 WS 連線
- [ ] 呼叫 `Network.getCookies` with `urls=["https://music.apple.com"]`，找 `media-user-token`
- [ ] 寫入 `data/apple_music_tokens.json`，關閉 CDP 連線

### 把握度：中高

CDP `Network.getCookies` 是穩定 API，能讀 HttpOnly cookie；無 WebDriver flag，不觸發 bot 偵測。現有 `data/auth_profile` 可直接沿用。

### 風險與限制

- 需 Python 端處理 CDP WebSocket 協定
- Chrome 更新偶爾改變 CDP 細節（但 `Network.getCookies` 屬於穩定 API）
- `--remote-debugging-port` 與其他 Chrome 實例可能衝突（需確認 port 未被佔用）

### Token 過期恢復流程

Cookie 過期時，排程自動略過並發 LINE 通知。恢復步驟：
1. 腳本以 `--remote-debugging-port=9222` 開啟 Chrome（`data/auth_profile`）
2. 若 profile 內 cookie 仍有效，自動讀取完成；若已過期，提示使用者在視窗重新登入 `music.apple.com`
3. 使用者登入完成後按 Enter，腳本讀取 cookie 並寫入 token 檔
4. 接續執行 `sync-apple-music.sh` 完成同步

---

## 方案 B：mitmproxy 側錄 Music.app 流量（長期穩定升級路線）

### 核心機制

macOS Music.app 是 Apple 原生 client，其 API 請求帶有 `X-Apple-Music-User-Token`，有效期約 **180 天**（遠長於 web 版）。一次性設置 mitmproxy，攔截 Music.app 對 `api.music.apple.com` 的請求，取得 `X-Apple-Music-User-Token` 後寫入檔案並自動結束。

**重要**：Music.app 原生 client 的 `Authorization` header 使用的是 client credential，格式與 web MusicKit developerToken 不相容。`developerToken` 仍必須從現有 `fetch_developer_token()`（Vite bundle JWT）取得，不可從攔截的 `Authorization` header 直接使用。

### 實作步驟

- [ ] `brew install mitmproxy`
- [ ] 將 mitmproxy CA 加入系統 Keychain 並信任
- [ ] 寫 mitmproxy addon script：攔截 `api.music.apple.com` 請求，**只取** `X-Apple-Music-User-Token`（= userToken），`developerToken` 另呼叫 `fetch_developer_token()` 取得，兩者合併寫入 `data/apple_music_tokens.json` 後 shutdown
- [ ] 恢復腳本自動以 `networksetup` 設定 / 還原系統 proxy
- [ ] 使用者觸發 Music.app 任一操作（切播放清單、搜尋）即完成側錄
- [ ] 測試 token 有效性（`GET /v1/me/library/playlists`）

### 把握度：中高

Music.app 是 Apple 原生 client，無 bot 偵測問題。Token 壽命約半年，能大幅降低日常授權頻率。首次設定稍繁瑣（CA 信任），適合前兩方案穩定後的升級。

### 風險與限制

- 首次設定涉及系統 CA 信任，步驟多
- 改變系統 proxy 可能短暫影響其他網路流量
- 若 Music.app 未來啟用 certificate pinning，此路線失效（目前未 pinning）
- Music.app 原生 token 與 web API 的相容性需實測驗證（smoke test 優先確認）

### Token 過期恢復流程

Token 約 180 天過期，排程自動略過並發 LINE 通知。恢復步驟：
1. 執行 `./recover-apple-music-sync.sh`
2. 腳本啟動 mitmproxy + 提示使用者在 Music.app 做任一操作
3. 攔截成功後自動關閉 proxy，寫入 token 檔
4. 接續執行 `sync-apple-music.sh` 完成同步

---

## 方案 D：pywebview / WKWebView 原生容器（保留方案）

### 核心機制

以 `pywebview` 嵌入 WKWebView（同 Safari 核心）載入 `music.apple.com`，使用者在視窗內登入後，Python 呼叫 `webview.get_cookies()` 取 `media-user-token`。非 Selenium、非 CDP，無 `navigator.webdriver` flag。

### 把握度：中

從未實測；Apple 可能對 embedded WebKit 有限制。列為前三方案全數受阻時的最後保險。

---

## 建議實作順序

| 優先 | 方案 | 把握度 | 理由 |
|------|------|--------|------|
| 1 | **A — Safari cookie** | 高 | 技術最確定，30 秒可驗證可行性 |
| 2 | **C — Chrome CDP** | 中高 | A 的 fallback，能讀 HttpOnly cookie |
| 3 | **B — mitmproxy** | 中高 | Token 壽命最長（~180 天），穩定後升級 |
| 4 | **D — pywebview** | 中 | 最後保險，從未實測 |

---

## 關鍵驗證（所有方案通用）

取得 token 後執行 smoke test：

```bash
curl -s \
  -H "Authorization: Bearer <devToken>" \
  -H "Media-User-Token: <userToken>" \
  "https://api.music.apple.com/v1/me/library/playlists?limit=1"
```

- **HTTP 200 + JSON `data` 陣列** → token 有效，可直接跑 `api.py` 全流程
- **HTTP 401** → token 無效或過期
- **HTTP 403** → 訂閱/地區/家族共享問題

---

## 相關檔案

| 檔案 | 說明 |
|------|------|
| `src/music_collector/apple_music/auth_server.py` | 授權入口，新方案在此替換 |
| `src/music_collector/apple_music/api.py` | REST API 層，token 來源變更後**不需修改** |
| `data/apple_music_tokens.json` | Token 儲存（格式不變） |
| `recover-apple-music-sync.sh` | 恢復腳本入口，需同步更新說明 |
| `CLAUDE.md` | 架構說明，需同步更新 |
