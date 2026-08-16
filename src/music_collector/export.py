"""匯出模組：將季度備份匯出為 CSV 或純文字格式。

支援格式：
- CSV：適用於 Soundiiz 等線上轉換工具
- TXT：純文字清單，方便手動搜尋
"""

import csv
import json
import logging
import re
from datetime import datetime
from pathlib import Path

from .config import BACKUP_DIR

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


def export_txt(query: str, spotify_only: bool = True) -> Path | None:
    """匯出備份為純文字格式。

    Args:
        query: 季度查詢字串（如 'Q1'、'2026Q1'）
        spotify_only: 若為 True，僅匯出在 Spotify 找到的曲目

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
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    label = f"{backup_path.parent.name}_{backup_path.stem}"
    export_path = EXPORT_DIR / f"{label}_{timestamp}.txt"

    # 寫入純文字
    lines = [f"{t['artist']} - {t['title']}" for t in data]
    export_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"\n✅ 已匯出 {len(data)} 首曲目至：")
    print(f"   {export_path}")

    return export_path


def export_playlist(
    query: str,
    fmt: str = "csv",
    include_all: bool = False,
    playlist_name: str | None = None,
) -> Path | None:
    """匯出備份為指定格式。

    Args:
        query: 季度查詢字串
        fmt: 格式（'csv' 或 'txt'）
        include_all: 若為 True，包含未在 Spotify 找到的曲目
        playlist_name: 播放清單名稱（作為匯出檔名）

    Returns:
        匯出檔案路徑
    """
    spotify_only = not include_all

    if fmt.lower() == "txt":
        return export_txt(query, spotify_only=spotify_only)
    else:
        return export_csv(query, spotify_only=spotify_only, playlist_name=playlist_name)


def export_spotify_url() -> None:
    """輸出主歌單與 All Time 累積歌單的 Spotify 連結，供 Soundiiz 等服務同步至其他平台。"""
    from .config import ALL_TIME_PLAYLIST_NAME
    from .spotify import get_spotify_client, get_or_create_playlist

    try:
        sp = get_spotify_client()

        for name in (None, ALL_TIME_PLAYLIST_NAME):
            playlist_id = get_or_create_playlist(sp, name=name)
            playlist = sp.playlist(
                playlist_id, fields="external_urls,name,tracks(total)"
            )
            print(f"\n🎵 {playlist['name']}")
            print(f"   曲目數：{playlist['tracks']['total']} 首")
            print(f"   連結：{playlist['external_urls']['spotify']}")

        print()
        print("📱 同步至 Apple Music / YouTube Music / Tidal：")
        print("   Soundiiz — https://soundiiz.com/ → Auto-Sync")
        print(f"   來源請選「{ALL_TIME_PLAYLIST_NAME}」（累積歌單，不受季度歸檔影響）")
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
