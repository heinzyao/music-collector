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
