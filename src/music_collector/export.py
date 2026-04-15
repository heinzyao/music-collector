"""匯出模組：將備份檔案匯出為 CSV 或純文字格式，供 Apple Music 匯入工具使用。

支援格式：
- CSV：適用於 TuneMyMusic、Soundiiz 等線上轉換工具
- TXT：純文字清單，方便手動搜尋
"""

import csv
import json
import logging
import re
from datetime import datetime
from pathlib import Path

from .config import BACKUP_DIR, PLAYLIST_NAME
from .spotify import get_spotify_client, get_or_create_playlist

logger = logging.getLogger(__name__)

# 匯出檔案目錄
EXPORT_DIR = BACKUP_DIR.parent / "exports"


def export_combined_spotify(playlist_name: str | None = None) -> Path | None:
    """合併 Spotify 主歌單與所有歸檔歌單，匯出為單一 CSV。

    用於一次性復原 Apple Music 累積歌單：將主歌單（當季）與所有
    「Critics' Picks — YYYY QN」歸檔歌單的曲目合併去重後匯出。

    Args:
        playlist_name: CSV 檔名／Apple Music 歌單名稱

    Returns:
        匯出檔案路徑，或 None（若失敗）
    """
    name = playlist_name or PLAYLIST_NAME

    try:
        sp = get_spotify_client()
    except Exception as e:
        logger.error(f"Spotify 連線失敗：{e}")
        print(f"錯誤：無法連線 Spotify — {e}")
        return None

    def _fetch_tracks(pid: str) -> list[tuple[str, str]]:
        tracks: list[tuple[str, str]] = []
        results = sp.playlist_items(pid, fields="items(track(name,artists(name))),next")
        while results:
            for item in results["items"]:
                track = item.get("track")
                if not track:
                    continue
                artist = ", ".join(a["name"] for a in track["artists"])
                tracks.append((artist, track["name"]))
            if results.get("next"):
                results = sp.next(results)
            else:
                break
        return tracks

    all_tracks: list[tuple[str, str]] = []

    main_id = get_or_create_playlist(sp, name=name)
    main_tracks = _fetch_tracks(main_id)
    all_tracks.extend(main_tracks)
    logger.info(f"主歌單：{len(main_tracks)} 首")

    offset = 0
    while True:
        playlists = sp.current_user_playlists(limit=50, offset=offset)
        if not playlists:
            break
        for pl in playlists["items"]:
            if pl["name"].startswith("Critics' Picks —") and pl["name"] != name:
                archive_tracks = _fetch_tracks(pl["id"])
                all_tracks.extend(archive_tracks)
                logger.info(f"歸檔歌單 {pl['name']}：{len(archive_tracks)} 首")
        if not playlists.get("next"):
            break
        offset += 50

    if not all_tracks:
        print("未找到任何曲目")
        return None

    seen: set[tuple[str, str]] = set()
    unique: list[tuple[str, str]] = []
    for artist, title in all_tracks:
        key = (artist.lower(), title.lower())
        if key not in seen:
            seen.add(key)
            unique.append((artist, title))

    EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    safe_name = re.sub(r'[<>:"/\\|?*]', "_", name)
    export_path = EXPORT_DIR / f"{safe_name}.csv"

    with export_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["Artist", "Title"])
        for artist, title in unique:
            writer.writerow([artist, title])

    print(
        f"\n✅ 已合併匯出 {len(unique)} 首曲目（原始 {len(all_tracks)} 首，去重後 {len(unique)} 首）"
    )
    print(f"   {export_path}")

    return export_path


def export_from_spotify(playlist_name: str | None = None) -> Path | None:
    """直接從 Spotify API 讀取歌單曲目並匯出為 CSV。

    相比 export_csv()（從備份 JSON 讀取），此函式使用 Spotify 官方元資料，
    確保 artist/title 與 Spotify 一致，提升 TuneMyMusic 匯入 Apple Music 的匹配率。

    Args:
        playlist_name: 播放清單名稱（同時用於搜尋 Spotify 歌單與 CSV 檔名）

    Returns:
        匯出檔案路徑，或 None（若失敗）
    """
    name = playlist_name or PLAYLIST_NAME

    try:
        sp = get_spotify_client()
        playlist_id = get_or_create_playlist(sp, name=name)
    except Exception as e:
        logger.error(f"Spotify 連線失敗：{e}")
        print(f"錯誤：無法連線 Spotify — {e}")
        return None

    # 分頁取得所有曲目
    tracks: list[tuple[str, str]] = []
    results = sp.playlist_items(
        playlist_id,
        fields="items(track(name,artists(name))),next",
    )
    while results:
        for item in results["items"]:
            track = item.get("track")
            if not track:
                continue
            artist = ", ".join(a["name"] for a in track["artists"])
            title = track["name"]
            tracks.append((artist, title))
        if results.get("next"):
            results = sp.next(results)
        else:
            break

    if not tracks:
        print("Spotify 歌單中無曲目")
        return None

    # 去重（case-insensitive）
    seen: set[tuple[str, str]] = set()
    unique: list[tuple[str, str]] = []
    for artist, title in tracks:
        key = (artist.lower(), title.lower())
        if key not in seen:
            seen.add(key)
            unique.append((artist, title))

    # 建立匯出目錄與檔案
    EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    safe_name = re.sub(r'[<>:"/\\|?*]', "_", name)
    export_path = EXPORT_DIR / f"{safe_name}.csv"

    # 寫入 CSV
    with export_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["Artist", "Title"])
        for artist, title in unique:
            writer.writerow([artist, title])

    print(
        f"\n✅ 已從 Spotify 匯出 {len(unique)} 首曲目（原始 {len(tracks)} 首，去重後 {len(unique)} 首）"
    )
    print(f"   {export_path}")

    return export_path


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


def get_current_quarter() -> str:
    """取得當前季度的標籤（如 '2026Q1'）。"""
    now = datetime.now()
    quarter = (now.month - 1) // 3 + 1
    return f"{now.year}Q{quarter}"


def export_csv(
    query: str, spotify_only: bool = True, playlist_name: str | None = None
) -> Path | None:
    """匯出備份為 CSV 格式。

    Args:
        query: 季度查詢字串（如 'Q1'、'2026Q1'）
        spotify_only: 若為 True，僅匯出在 Spotify 找到的曲目
        playlist_name: 播放清單名稱（TuneMyMusic 會使用檔名作為歌單名稱）

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

    # 使用播放清單名稱作為檔名（TuneMyMusic 會使用檔名作為歌單名稱）
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
    if not playlist_name:
        print("\n📱 匯入方式：")
        print("   1. 前往 https://www.tunemymusic.com/")
        print("   2. 選擇「Select source」→「File」→ 上傳此 CSV")
        print("   3. 選擇「Select destination」→「Apple Music」")
        print("   4. 完成匯入")

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
    print("\n📱 匯入方式：")
    print("   手動在 Apple Music 中搜尋並加入播放清單")

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
        playlist_name: 播放清單名稱（用於 --import 時設定 Apple Music 歌單名稱）

    Returns:
        匯出檔案路徑
    """
    spotify_only = not include_all

    if fmt.lower() == "txt":
        return export_txt(query, spotify_only=spotify_only)
    else:
        return export_csv(query, spotify_only=spotify_only, playlist_name=playlist_name)


def export_spotify_url() -> None:
    """輸出 Spotify 播放清單連結，供使用者透過 TuneMyMusic 或 Soundiiz 轉換至其他平台。

    支援轉換至：YouTube Music、Tidal、Apple Music 等。
    """
    from .spotify import get_spotify_client, get_or_create_playlist

    try:
        sp = get_spotify_client()
        playlist_id = get_or_create_playlist(sp)
        playlist = sp.playlist(playlist_id, fields="external_urls,name,tracks(total)")
        url = playlist["external_urls"]["spotify"]
        name = playlist["name"]
        total = playlist["tracks"]["total"]

        print(f"\n🎵 Spotify 播放清單：{name}")
        print(f"   曲目數：{total} 首")
        print(f"   連結：{url}")
        print()
        print("📱 轉換至其他平台：")
        print("   1. TuneMyMusic — https://www.tunemymusic.com/")
        print("      選擇 Spotify → YouTube Music / Tidal / Apple Music")
        print("   2. Soundiiz — https://soundiiz.com/")
        print("      選擇 Spotify → 任意目標平台")
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
