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

加入 SoulBounce（0.73 首/日 × 30 ≈ 22 首，以未去重的解析數為上界）：221 / 395 = **55.9%**，仍 ≥ 50%，**不設曲目上限**。
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
