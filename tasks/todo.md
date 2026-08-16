# Apple Music 整合重build → Soundiiz 外包

## 背景

`apple_music/api.py` 已不是整合，只剩「CSV → Tab 分隔 TXT + print 教學」，其餘 6 個函式都是恆回傳成功的 no-op stub。
根本缺陷：macOS 音樂 App 的「匯入播放清單」只比對既有資料庫，不查 Apple Music 目錄，冷門曲目結構性無法匹配。

決策：**砍掉整個 Apple Music 模組**，改由 Soundiiz Auto-Sync 從 Spotify 端鏡射。
因為 Soundiiz 盯單一歌單、而主歌單每季會被歸檔搬空，另建一個只進不出的
「Critics' Picks — All Time」累積歌單作為同步來源。

## 清單

- [x] `spotify.py`：`ALL_TIME_PLAYLIST_NAME`、`mirror_to_all_time()`、`backfill_all_time()`
- [x] `config.py`：`ALL_TIME_PLAYLIST_NAME` 常數
- [x] `main.py`：移除 5 個 Apple Music 函式與 4 個 CLI flag、`run(sync_apple_music=)` 參數
- [x] `main.py`：`--backfill-all-time` 取代 `--recover-apple-music`
- [x] `main.py`：Spotify 認證失敗改為捕捉 + 發通知（原本裸呼叫，token 撤銷會靜默炸掉排程）
- [x] `notify.py`：移除 `send_apple_music_notification()`、`_build_apple_music_message()`、`apple_music_status`
- [x] `notify.py`：新增 `send_error_notification()`（給 Spotify 授權失效用）
- [x] `export.py`：移除 `export_combined_spotify()` 與 TuneMyMusic 匯入教學文字
- [x] 刪除 `src/music_collector/apple_music/`
- [x] 刪除 6 個 Apple Music shell / .command 腳本 + 2 個 plist
- [x] `run-scheduled.sh`：移除 Step 2
- [x] 測試：刪 `test_apple_music_api.py`、改寫 `test_notify.py`、`test_spotify.py` 補 All Time 測試
- [x] 文件：CLAUDE.md、README.md

## 一次性手動步驟（程式碼外）

1. 重新授權 Spotify：`rm .spotify_cache && ./run.sh --backfill-all-time`（瀏覽器點一次）
2. `./run.sh --backfill-all-time` 把主歌單 + 所有歸檔歌單回填進 All Time
3. Soundiiz Premium → Auto-Sync：source = Spotify `Critics' Picks — All Time`，
   destination = Apple Music 同名歌單，頻率每週

## Review

- 淨刪除 13 個檔案；`--apple-music` 路徑完全消失，排程回到單一步驟
- 專案不再有任何 Apple Music 程式碼，只在 Spotify 端多維護一個累積歌單
- `mirror_to_all_time()` 的去重讓它同時是回填與修復工具（漏掉的曲目下次跑會自動補上）
