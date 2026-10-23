"""匯出模組：將季度備份匯出為 CSV（適用於各家線上歌單轉換工具），
以及把近期樂評曲目匯出成 critics.json 上傳 GCS（供雲端 music-recommender 使用）。"""

import csv
import json
import logging
import re
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from .config import BACKUP_DIR, CRITICS_GCS_URI

logger = logging.getLogger(__name__)

# 匯出檔案目錄
EXPORT_DIR = BACKUP_DIR.parent / "exports"


def _find_backup(query: str) -> Path | None:
    """尋找指定季度的備份檔案。

    query 格式：'Q1'、'2026Q1'、'2026/Q1' 皆可。
    若僅指定 Q1-Q4，則預設為當年。
    """
    q = query.upper().replace("/", "").replace("-", "").strip()

    candidates = sorted(BACKUP_DIR.glob("**/Q*.json"))

    for f in candidates:
        label = f"{f.parent.name}{f.stem}".upper()
        if q == label or q == f.stem.upper():
            return f

    return None


def _load_backup(path: Path) -> list[dict]:
    """讀取備份檔案內容。"""
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as e:
        logger.error(f"備份讀取失敗：{e}")
        return []


def export_csv(
    query: str, spotify_only: bool = True, playlist_name: str | None = None
) -> Path | None:
    """匯出備份為 CSV 格式。

    Args:
        query: 季度查詢字串（如 'Q1'、'2026Q1'）
        spotify_only: 若為 True，僅匯出在 Spotify 找到的曲目
        playlist_name: 播放清單名稱（多數轉換服務會以檔名作為歌單名稱）

    Returns:
        匯出檔案路徑，或 None（若失敗）
    """
    backup_path = _find_backup(query)
    if not backup_path:
        print(f"找不到備份：{query}")
        _show_available_backups()
        return None

    data = _load_backup(backup_path)
    if not data:
        return None

    # 篩選曲目
    if spotify_only:
        data = [t for t in data if t.get("spotify_uri")]

    if not data:
        print("無可匯出的曲目（全部未在 Spotify 找到）")
        return None

    # 建立匯出目錄與檔案
    EXPORT_DIR.mkdir(parents=True, exist_ok=True)

    # 使用播放清單名稱作為檔名（多數轉換服務會以檔名作為歌單名稱）
    if playlist_name:
        # 移除檔名中不允許的字元
        safe_name = re.sub(r'[<>:"/\\|?*]', "_", playlist_name)
        export_path = EXPORT_DIR / f"{safe_name}.csv"
    else:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        label = f"{backup_path.parent.name}_{backup_path.stem}"
        export_path = EXPORT_DIR / f"{label}_{timestamp}.csv"

    # 寫入 CSV
    with export_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["Artist", "Title"])
        for t in data:
            writer.writerow([t["artist"], t["title"]])

    print(f"\n✅ 已匯出 {len(data)} 首曲目至：")
    print(f"   {export_path}")

    return export_path


def export_spotify_url() -> None:
    """輸出主歌單與 All Time 累積歌單的 Spotify 連結與曲目數。"""
    from .config import ALL_TIME_PLAYLIST_NAME
    from .spotify import get_spotify_client, get_or_create_playlist, get_playlist_total

    try:
        sp = get_spotify_client()

        for name in (None, ALL_TIME_PLAYLIST_NAME):
            playlist_id = get_or_create_playlist(sp, name=name)
            playlist = sp.playlist(playlist_id, fields="external_urls,name")
            print(f"\n🎵 {playlist['name']}")
            print(f"   曲目數：{get_playlist_total(sp, playlist_id)} 首")
            print(f"   連結：{playlist['external_urls']['spotify']}")
    except Exception as e:
        logger.error(f"取得 Spotify 播放清單失敗：{e}")
        print(f"錯誤：{e}")


def _show_available_backups() -> None:
    """顯示可用的備份檔案。"""
    candidates = sorted(BACKUP_DIR.glob("**/Q*.json"))
    if candidates:
        available = ", ".join(f"{f.parent.name}/{f.stem}" for f in candidates)
        print(f"可用備份：{available}")
    else:
        print("尚無備份資料。")


CRITICS_DAYS = 90
CRITICS_LIMIT = 300


def build_critics(conn: sqlite3.Connection) -> dict:
    """取最近 90 天、有 Spotify URI 的曲目，新到舊最多 300 筆。

    added_at 是 SQLite CURRENT_TIMESTAMP（UTC），所以篩選也交給 SQLite 的 'now' 比較，
    輸出時補上 Z 標示 UTC。
    DB 去重鍵 (artist, title) 與 URI 不是一對一（見 AGENTS.md「播放清單去重」），
    同一 URI 只留最新一筆，再截上限。
    """
    rows = conn.execute(
        "SELECT artist, title, source, spotify_uri, added_at FROM tracks "
        "WHERE spotify_uri IS NOT NULL AND spotify_uri != '' "
        "AND added_at >= datetime('now', ?) "
        "ORDER BY added_at DESC, id DESC",
        (f"-{CRITICS_DAYS} days",),
    ).fetchall()
    latest = {}
    for row in rows:
        latest.setdefault(row[3], row)
    tracks = [
        {
            "artist": artist,
            "title": title,
            "source": source,
            "spotify_uri": uri,
            "added_at": str(added_at).replace(" ", "T") + "Z",
        }
        for artist, title, source, uri, added_at in list(latest.values())[:CRITICS_LIMIT]
    ]
    return {
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "tracks": tracks,
    }


def _upload_gcs(gcs_uri: str, data: bytes) -> None:
    """以本機 ADC 上傳到 gs://bucket/path。"""
    from google.cloud import storage

    bucket_name, _, blob_name = gcs_uri.removeprefix("gs://").partition("/")
    if not gcs_uri.startswith("gs://") or not bucket_name or not blob_name:
        raise ValueError(f"CRITICS_GCS_URI 格式應為 gs://bucket/path：{gcs_uri}")
    blob = storage.Client().bucket(bucket_name).blob(blob_name)
    blob.upload_from_string(data, content_type="application/json")


def export_critics(out: Path | None = None) -> None:
    """匯出 critics.json。

    指定 out 時只寫本機檔案、不上傳；否則在設了 CRITICS_GCS_URI 時上傳 GCS，沒設就跳過。
    任何失敗只記警告，不拋例外（每日流程與通知不受影響）。
    """
    if out is None and not CRITICS_GCS_URI:
        logger.info("未設定 CRITICS_GCS_URI，略過 critics.json 匯出")
        return
    try:
        from .db import init_db

        conn = init_db()
        try:
            payload = build_critics(conn)
        finally:
            conn.close()
        data = json.dumps(payload, ensure_ascii=False, indent=1).encode("utf-8")
        if out is not None:
            out.write_bytes(data)
            logger.info(f"已輸出 {len(payload['tracks'])} 首至 {out}")
        else:
            _upload_gcs(CRITICS_GCS_URI, data)
            logger.info(f"已上傳 {len(payload['tracks'])} 首至 {CRITICS_GCS_URI}")
    except Exception as e:
        logger.warning(f"critics.json 匯出失敗：{e}")
