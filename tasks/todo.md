# 新增樂評來源：DIY 與 Aquarium Drunkard

## 背景

現有 13 個來源。掃過 36 個候選 RSS feed 後，只有兩個值得加：

- **DIY**（diymag.com，50 篇/日）— 英國獨立樂。藝人名直接在 RSS 的 category tag 裡，
  曲名在引號內，不需要 NME/SPIN 那套動詞邊界猜測，是所有候選中最不易壞的。
- **Aquarium Drunkard**（15 篇/日）— 標題一律 `Artist :: Title`，解析零難度，
  但混雜爵士老錄音與現場版，需靠 tag 與括號過濾，淨產出預期只有個位數。

其餘候選不採用的理由記於同次對話：Hypebeast 訊噪比差、Under the Radar 曲名不在 RSS 標題、
Beats Per Minute 與 Quietus 重疊、KEXP/Exclaim!/FLOOD 等 7 站無可用 feed。

## 清單

- [x] `scrapers/diy.py` — RSS，News 分類 + tag 取藝人 + 引號取曲名
- [x] DIY：處理「宣布專輯 X 並釋出單曲 Y」的雙引號標題，須取單曲而非專輯
- [x] `scrapers/aquariumdrunkard.py` — RSS，` :: ` 分隔 + tag/括號過濾
- [x] `scrapers/__init__.py` — 註冊兩個擷取器
- [x] `tests/scrapers/test_diy.py`、`test_aquariumdrunkard.py`
- [x] 實跑 `--dry-run` 確認兩個來源都有非零產出
- [x] 文件：CLAUDE.md 擷取器表格、README 來源清單、13 → 15

## Review

- 兩個擷取器共 15 個來源，`--dry-run` 實跑 15 個全部非零；新來源當次貢獻
  DIY 19 首、Aquarium Drunkard 7 首
- **DIY 的雙引號問題確實存在且已處理**：「Jamie T returns with new album
  ‘Ghosts (100 Days of Morning)’ and shares single ‘3310’」這類標題有兩組引號，
  依引號前 30 字內的用字（album/LP/EP vs single/track/song）決定取哪一組。
  實跑驗證取到 `3310` 而非專輯名
- **Aquarium Drunkard 用「藝人名必須對得上 category tag」擋未知專欄**，
  而非只靠黑名單 —— 實測 `Transmissions ::`（Podcast）與 `Black Rock ::`
  都是靠這條規則擋下的，日後新增專欄不必回頭改程式
- 曲名側含 `(` 一律跳過：該站大量現場與 archival 錄音的場地／年份註記都在括號裡，
  這些在 Spotify 幾乎搜不到。寧可過濾過度，不讓雜訊進歌單
- 掃過的 36 個 feed 中，7 站（KEXP、Exclaim!、Northern Transmissions、FLOOD、
  Mixmag、Passion of the Weiss、Sputnikmusic）已無可用 RSS，不必再試
- 歌單描述同步更新為 15 家並加入兩個新來源名稱（224 字元，未超過 Spotify 300 上限）
