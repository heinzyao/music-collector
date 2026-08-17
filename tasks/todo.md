# Apple Music 整合移除 → Spotify 單一平台

## 背景

`apple_music/api.py` 已不是整合，只剩「CSV → Tab 分隔 TXT + print 教學」，其餘 6 個函式都是恆回傳成功的 no-op stub。
根本缺陷：macOS 音樂 App 的「匯入播放清單」只比對既有資料庫，不查 Apple Music 目錄，冷門曲目結構性無法匹配。

原本決定改用 Soundiiz Auto-Sync 外包，後續確認**不採用 Soundiiz Premium**，
且歌單已達 1555 首（2026-08-02），超出所有免費轉換服務額度
（FreeYourMusic 600、TuneMyMusic 500、Soundiiz 200、SongShift 200）。

**最終決策：放棄 Apple Music，Spotify 為唯一目標平台。**
「Critics' Picks — All Time」累積歌單保留 —— 它在 Spotify 端本身就有價值：
主歌單每季被歸檔搬空、歷史散落在各季歌單，這份是唯一能一眼看完全部的歌單。

## 清單

- [x] `spotify.py`：`mirror_to_all_time()`、`backfill_all_time()`
- [x] `config.py`：`ALL_TIME_PLAYLIST_NAME` / `ALL_TIME_PLAYLIST_DESCRIPTION`
- [x] `main.py`：移除 5 個 Apple Music 函式與 4 個 CLI flag、`run(sync_apple_music=)` 參數
- [x] `main.py`：新增 `--backfill-all-time`
- [x] `main.py`：Spotify 認證失敗改為捕捉 + 發通知（原本裸呼叫，token 撤銷會靜默炸掉排程）
- [x] `notify.py`：移除 Apple Music 通知，新增 `send_error_notification()`
- [x] `export.py`：移除 `export_combined_spotify()` 與轉換服務教學文字
- [x] 刪除 `src/music_collector/apple_music/`、6 個腳本、2 個 plist
- [x] `run-scheduled.sh`：回到單一步驟
- [x] 測試：刪 `test_apple_music_api.py`、改寫 `test_notify.py`、`test_spotify.py` 補 All Time 測試
- [x] CI：`pyproject.toml` 釘住 ruff 規則集（`uvx ruff` 抓最新版導致 CI 斷線）
- [x] 文件：CLAUDE.md、README.md 移除所有 Apple Music／Soundiiz 框架

## 待辦（手動）

1. 重新授權 Spotify：`rm .spotify_cache && ./run.sh`（refresh token 於 2026-08 被撤銷，
   排程 8/09、8/16 連兩週失敗）
2. `./run.sh --backfill-all-time` 回填 All Time 累積歌單

## Review

- 淨刪除 13 個檔案；`--apple-music` 路徑完全消失，排程回到單一步驟
- CLAUDE.md 已明文記載四種失敗做法與理由，避免日後又被提議加回來
- `mirror_to_all_time()` 的去重讓它同時是回填與修復工具（漏掉的曲目下次跑會自動補上）
