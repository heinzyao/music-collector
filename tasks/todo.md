# 修復 stale 來源（NME、Resident Advisor）→ 改以 When We Dip 替代

## 背景

`--health` 標出 NME（60 天）與 Resident Advisor（81 天）stale。先查根因，修不好就換電子類來源。
門檻同「來源選擇原則」：配對率 ≥ 60%、目測誤配 ≤ 1 首。

## 清單

- [x] NME 根因 → 無法修復，移除
- [x] RA 根因 → 無法修復，移除
- [x] 電子類替代來源初篩 + 量測（`~/.hermes/cache/scratch/mc_measure_electronic.py`，唯讀：只呼叫 Spotify search/track）
- [x] When We Dip 擷取器 + 測試（RSS 內嵌 fixture，不打網路）
- [x] 刪除 nme.py／residentadvisor.py 與其測試、fixture（git 歷史保留）
- [x] `scrapers/__init__.py`、README 中英、AGENTS.md（表格、已移除來源）、`config.py` 歌單描述（15 → 14 家，218 字元）
- [x] pytest、ruff、dry-run、Opus 第二意見

## 根因（2026-10-23 查證）

- **NME**：擷取器沒壞，是 NME 停更 track review。`https://www.nme.com/reviews/track` 頁面最新日期 2026-08-18，其後依序是 04-08、02-19…
  - 新聞 RSS `https://www.nme.com/news/music/feed` 不可行：固定只給 10 篇（約 1 天），`?paged=2/3` 回傳同一批；category 只有 Music News／曲風，**沒有藝人 tag**，DIY 的 tag 比對法用不上
  - 當下 10 篇裡 0 篇是新歌消息（Mercury 獎、巡演、書、影片、電視）；用引號抓會把巡演名 ‘Dopamine Chamber’、書名 ‘New Feeling’、節目 ‘Chicken Shop Date’ 當曲名
  - `post-sitemap306.xml` 近 17 天 164 篇音樂新聞，slug 含 new-single／shares 等只有 13 篇、真正的新歌約 8 篇（約 0.5 首/日），且是 U2、Rolling Stones、Harry Styles 這類主流，與 Rolling Stone 重疊。page 1 + RSS 樣本 ≤ 1 首，無法達門檻
- **Resident Advisor**：`/tracks` 是 301 轉到 `/reviews/singles`，所以 HTML 相同，不是改版。資料其實在 SSR 的 `__NEXT_DATA__`（不用 Playwright）
  - `https://ra.co/graphql` `reviews(limit:10)`：**所有類型**評論最新一篇是 2026-07-28（Picture - Uuuuuuuu，id 36364），單曲最新 2026-07-25（Fauzia），2026 全年單曲評論只有 6 篇；專輯評論也停在 07-28
  - 舊擷取器每天抓到的是頁面上的舊評論，全被 DB 去重擋掉。RA 沒有其他「推薦單曲」區塊（News／Podcast／Events 不是曲目）

## 替代來源量測（2026-10-23）

| 來源 | 文章 | 曲目 | 配對 | 配對率 | 估計日產 | 結果 |
|------|------|------|------|--------|----------|------|
| When We Dip | 30（10 天，3 頁） | 15 | 14 | 93% | 1.5 首（配對後 1.4） | ✅ 加入 |
| Inverted Audio（Premiere） | 30（123 天，3 頁） | 10 | 7 | 70% | 0.08 首 | ❌ 達標但量太少，不值得一個擷取器 |
| Attack Magazine | 10 | 0 | — | — | — | ❌ 製作教學、器材、專訪 |
| Crack Magazine | 99 | 0 | — | — | — | ❌ 只剩活動／音樂節新聞 |
| Decoded Magazine | 20 | — | — | — | — | ❌ Music Premieres 多數無引號（「X drops Godsexy via Selador」），其餘為新聞／器材 |
| FACT（factmag.com） | 30 | 0 | — | — | — | ❌ 只剩 180 Studios 展覽，最新 2026-09-30 |
| Stamp the Wax | 10 | — | — | — | — | ❌ 最新一篇 2023-05 |
| Electronic Beats、The Vinyl Factory | — | — | — | — | — | ❌ feed 404 |
| Pitchfork track reviews | — | — | — | — | — | 不分曲風，已有 Pitchfork 擷取器 |
| Bandcamp Daily | — | — | — | — | — | feed 沒有電子專欄，且已有擷取器 |

- When We Dip 14 首配對目測全部正確，0 誤配（Simon Vuarambon — Metro → Josh Wink, Simon Vuarambon「Metro - Simon Vuarambon Rework」、Matthew Sona — Aldilá → Artic White, Matthew Sona「Aldilá - Matthew Sona Remix」也正確）
- 唯一未配對是誤解析：The Afters — ‘Robot84: Finding The Rhythm Again’（平台上線新聞，不是曲目；沒配到所以不會進歌單）
- 正確略過：‘Malone’ EP、‘Itkar’ EP、‘Summer’s End Sampler’ VA、album ‘CONTACTO’、Interviews／Events／Podcasts
- 漏抓（可接受）：標題以「Label boss Peter Makto」開頭對不上 tag

## 占比估算

DB 最近 30 天新曲目 373 首。NME、RA 這 30 天貢獻 0 首，移除不影響分母。
獨立搖滾類（Stereogum 165、The Quietus 27、DIY 11、The Line of Best Fit 8、Pitchfork 2、Gorilla vs. Bear 2）= 215 首 = **57.6%**。

加入 When We Dip（1.5 首/日 × 30 = 45 首，以未去重的解析數為上界）：215 / 418 = **51.4%**，比照 SoulBounce **不設曲目上限**
（SoulBounce 預估 22 首、實際 30 天 7 首，上界估算偏高）。門檻已於 2026-10-23 由 50% 下修為約 30%：目前 51～58% 遠高於門檻，不需要上限；
若 `--stats sources` 顯示獨立搖滾跌破 30%，再對 When We Dip 設每次上限。

## Review

- dry-run：When We Dip 抓到 2 首（Jon Who — Glass Houses、M.O.S. — Inka），皆為新曲目；`data/tracks.db` md5 前後一致
- pytest 164 passed、ruff 乾淨
- Playwright 已無擷取器使用；`_get_rendered()`、`ENABLE_PLAYWRIGHT`、`--extra browser` 先保留（拆掉要動 run.sh／pyproject／文件，範圍外）

### Opus 第二意見

- 採納：`ALBUM_BEFORE` 拿掉 `mix`（「a hypnotic mix of house on ‘Track’」會被誤殺；DJ mix 已由 Podcasts 分類排除）；補測試
- 採納：README 中英目錄樹補齊 diy.py、aquariumdrunkard.py、soulbounce.py（原本就缺）
- 駁回：分類 tag（House、News）參與藝人比對 —— `_match_artist_tag` 取最長吻合且檢查字界
- 駁回：移除的來源會一直被標 stale —— health 只檢查 `ALL_SCRAPERS` 裡的名稱
- 不改（既有模式）：`feedparser.parse(URL)` 無逾時、`entries[:MAX]` 在過濾前切 —— 所有 RSS 擷取器皆如此
- 不改（既有慣例）：todo 內的 scratch 腳本路徑，前幾節都這樣記

# Spotify 改走 /playlists/{id}/items（相容 2026 新 app）

## 背景

2026 新建的 Developer app 封掉 `/playlists/{id}/tracks` 與 `/users/{id}/playlists`（Hermes 2026-10-23 實測）。
改走 `/items`、`/me/playlists`，舊 app 也相容。不切換 `.env`（Hermes 驗證後再切）。

## 清單

- [x] `spotify.py` helper：`_playlist_items`（分頁、item/track 鍵）、`_add_items`／`_remove_items`（≤100）、`_create_playlist`、`get_playlist_total`
- [x] 取代所有 `/tracks` 與 `/users/{id}` 呼叫（spotify.py、stats.py、main.py、export.py）
- [x] `SPOTIFY_CACHE_PATH` 環境變數覆寫（config.py；auth.py 沿用）
- [x] 單元測試（全 mock）
- [x] 實測：暫存歌單在兩個 app 上建立→加入（含重複）→讀回→移除→unfollow，無殘留
- [x] 舊 app `./run.sh --dry-run`、唯讀 `--stats adoption`
- [x] AGENTS.md 新增「Spotify Developer app 與端點」
- [x] pytest、ruff、Opus 第二意見、commit

## Review

- 實測腳本 `~/.hermes/cache/scratch/mc_items_live.py`（不進 repo）
  - 舊 app（…00ed）：讀回 3 首（去重正確）、total 3、項目鍵 item+track、移除後 0、unfollow 後無殘留
  - 新 app（…54c6）：同上，項目鍵只有 item
- `--dry-run`：exit 0、DB md5 前後一致（dry-run 不呼叫 Spotify）
- `--stats adoption`（舊 app，唯讀）：讀完所有自有歌單，合計 2395／106
- 沒用到 `/artists` 批次、`/browse/new-releases`、genres，無需降級
- 未用 `playlist_replace_items`（PUT /items），故未測

### Opus 第二意見

- 採納：`archive_previous_quarters()` 寫入歸檔缺批次自身去重（違反兩層去重規則）→ 補 `dict.fromkeys`；`_remove_items()` 送出前也去重
- 採納：`SPOTIFY_CACHE_PATH` 展開 `~`，相對路徑以專案根目錄為準（launchd CWD 不同時才不會找不到 token）
- 駁回：依賴 spotipy 私有 `_get/_post/_delete` —— spotipy 沒有 `/items` 的公開方法，版本由 uv.lock 鎖定
- 駁回（既有行為、範圍外）：歸檔時移除所有出現位置可能連當季重複的那份一起刪 —— 寫入端已兩層去重，主歌單不會有重複
- 駁回：`get_playlist_total()` 兩鍵皆缺時錯誤訊息不清 —— 兩個 app 實測都有值，呼叫端皆有 try/except

# 試加歐美樂評來源（補 R&B／電子／爵士）

## 背景

R&B／soul、電子、爵士幾乎沒有活躍來源（Resident Advisor 81 天沒新曲目）。依 AGENTS.md「來源選擇原則」
試加四個候選，先量測、達標才加入。門檻：三頁內配對率 ≥ 60%、目測誤配 ≤ 1 首。

## 清單

- [x] AGENTS.md 新增「來源選擇原則」
- [x] SoulBounce 擷取器（沿用中止草稿：tag 大小寫／重音／撇號摺疊比對、DIY 雙引號規則）+ 測試
- [x] 量測（暫時腳本 `~/.hermes/cache/scratch/mc_measure.py`，只呼叫 Spotify search/track，不寫歌單與 DB）
- [x] 占比估算 → 不需上限
- [x] 註冊、README 中英、AGENTS.md 表格、`config.py` 歌單描述（14 → 15 家）
- [x] pytest、ruff、dry-run（DB 副本）

## 量測結果（2026-10-22）

| 來源 | 文章 | 曲目 | 配對 | 配對率 | 估計日產 | 結果 |
|------|------|------|------|--------|----------|------|
| SoulBounce | 30（22 天） | 16 | 14 | 88% | 0.73 首（配對後 0.64） | ✅ 加入 |
| Data Transmission | 10（5 天，僅第 1 頁） | 5 | 2 | 40% | 1.0 首（配對後 0.4） | ❌ 配對率未達 60% |
| Dummy | 10（僅第 1 頁） | ≤1 | — | — | — | ❌ 有效單曲 < 3 |
| JazzTimes | 30 | 0 | — | — | — | ❌ 有效單曲 < 3 |

- SoulBounce 14 首配對目測全部正確，0 誤配；未配對：Doechii — BOMBS、Snoh Aalegra — Run Free（Spotify 搜不到）
- Data Transmission：`?paged=2` 起回傳 HTML 首頁，實際只有 10 篇；未配對 Diverse — Resurgence、Moog Conspiracy — Hyperspeed、Chris Valencia — Flip & Reverse（地下廠牌新發行，Spotify 尚未上架或藝名不同）。另 `Dominique & Velvet Code` 只取到第一個 tag `Dominique`；`tommi`、`Woody Cook And Zed Bias` 因 tag 無藝人而漏抓
- Dummy：`?paged=N` 會 301 到 dmy.co 並忽略參數，三頁都是同一批 10 篇；唯一候選 Jamz Supernova ‘Dance Around The World’ 為專輯／選輯，其餘是專輯樂評、新聞、專題
- JazzTimes：feed 無 category，標題全是評論／專訪／現場報導；唯一引號是人名綽號（James “Blood” Ulmer），非曲目

## 占比估算

DB 最近 30 天新曲目 373 首（12.4 首/日）。獨立搖滾類（Stereogum 172、The Quietus 28、DIY 11、
The Line of Best Fit 7、Pitchfork 2、Gorilla vs. Bear 1）= 221 首 = **59.2%**。

加入 SoulBounce（0.73 首/日 × 30 ≈ 22 首，以未去重的解析數為上界）：221 / 395 = **55.9%**，仍 ≥ 50%（當時門檻，現已下修為約 30%），**不設曲目上限**。
（保守算法：Aquarium Drunkard、Bandcamp Daily 不計入獨立搖滾。）

## Review

- `--dry-run` 並非完全唯讀：`collect_tracks()` 會把健康紀錄寫入 `source_checks`。因此改用 DB 副本
  （patch `db.DB_PATH`）跑同一個 `main()`；正式 DB md5 前後一致。SoulBounce 抓到 8 首、7 首為新曲目
- pytest 全過（163）、ruff 乾淨

### Opus 第二意見

- 採納：引號前的判斷窗口改為「上一組引號之後」，修正「Album ‘X’ With Lead Single ‘Y’」漏抓（原本 Anderson .Paak 那句剛好差 1 字才過）；補測試
- 採納：tag 比對前先做 NFC，避免 NFD 組合字元對不上；補測試
- 修正後重跑三頁解析，結果與量測一致（16 首）
- 駁回：綽號／`‘n’` 被當曲名 —— 綽號會讓標題開頭對不上 tag 而整篇放棄；實測 0 誤配
- 不改（既有模式）：`feedparser.parse(URL)` 無逾時、`entries[:MAX]` 在過濾前切 —— 所有 RSS 擷取器皆如此，範圍外
- 駁回：「diff 看不到量測」—— 送審 diff 未含 todo，量測見上

# 強化來源有效性檢查

## 背景

NME（最後新曲目 2026-08-23）與 Resident Advisor（2026-08-02）每天都抓得到曲目，
但全是 DB 裡已有的舊歌，`--health` 仍顯示 healthy —— 健康檢查只看抓到幾首、不看有沒有新歌。

## 清單

- [x] `config.SOURCE_STALE_DAYS`（預設 30）
- [x] `health.py`：tracks 表最近 added_at 超過門檻或從未有曲目 → `stale`（警告級，優先序低於 unhealthy / 連續空白）
- [x] `--health` 每個來源列「最後新曲目」；LINE 通知列出 stale 來源
- [x] `--stats sources` 配對率（既有欄位，補測試）
- [x] `--stats adoption`：唯讀讀自己的歌單，算各來源採用率
- [x] 測試、README 中英、AGENTS.md

## Review

- 實跑 `--health`：stale 僅 NME（60 天）、Resident Advisor（81 天）
- `--stats sources` 原本就有「配對率」欄，未改程式，只補測試
- 實跑 `--stats adoption`：自己歌單 6790 首，合計採用率 4.4%

### Opus 第二意見

- 採納：adoption 另排除 `config.PLAYLIST_NAME` / `ALL_TIME_PLAYLIST_NAME`（環境變數改名時不會把工具歌單算進採用）
- 採納：補「連續空白優先於 stale」與 LINE 通知 stale 分支的測試
- 駁回：「缺 playlist-read-private scope」—— `SCOPE` 已含
- 不改（範圍外／依需求）：Liked Songs 未計入；從未有曲目即 stale；日期為 UTC（與既有「最後活動」一致）
