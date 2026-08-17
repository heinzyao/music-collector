"""Spotify 整合模組：認證、搜尋曲目、管理播放清單、季度歸檔。

使用 spotipy 函式庫透過 OAuth 2.0 Authorization Code Flow 連線。
首次執行需瀏覽器授權，之後 Token 自動從快取更新。
"""

import logging
import re
from datetime import datetime, timezone

import spotipy
from spotipy.oauth2 import SpotifyOAuth

from .config import (
    ALL_TIME_PLAYLIST_DESCRIPTION,
    ALL_TIME_PLAYLIST_NAME,
    PLAYLIST_DESCRIPTION,
    PLAYLIST_NAME,
    SPOTIFY_CACHE_PATH,
    SPOTIFY_CLIENT_ID,
    SPOTIFY_CLIENT_SECRET,
    SPOTIFY_REDIRECT_URI,
    get_quarter,
)

logger = logging.getLogger(__name__)

# 播放清單讀寫權限
SCOPE = "playlist-modify-public playlist-modify-private"


def get_spotify_client() -> spotipy.Spotify:
    """建立並回傳已認證的 Spotify 客戶端。"""
    if not SPOTIFY_CLIENT_ID or not SPOTIFY_CLIENT_SECRET:
        raise RuntimeError(
            "尚未設定 Spotify 憑證。"
            "請將 .env.example 複製為 .env 並填入 SPOTIFY_CLIENT_ID 和 SPOTIFY_CLIENT_SECRET。"
            "前往 https://developer.spotify.com/dashboard 建立應用程式。"
        )

    auth_manager = SpotifyOAuth(
        client_id=SPOTIFY_CLIENT_ID,
        client_secret=SPOTIFY_CLIENT_SECRET,
        redirect_uri=SPOTIFY_REDIRECT_URI,
        scope=SCOPE,
        cache_path=str(SPOTIFY_CACHE_PATH),
    )
    return spotipy.Spotify(auth_manager=auth_manager)


# ── 搜尋與驗證 ──


def _normalize(text: str) -> str:
    """正規化文字：小寫、移除標點與多餘空白，用於比對。"""
    text = text.lower()
    text = re.sub(r"[^\w\s]", "", text)   # 移除標點
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _is_match(expected: str, actual: str) -> bool:
    """檢查兩段文字是否足夠相似（子字串包含即通過）。"""
    a, b = _normalize(expected), _normalize(actual)
    return a in b or b in a


def _verify_result(
    item: dict, artist: str, title: str,
) -> bool:
    """驗證 Spotify 搜尋結果是否與來源的藝人 + 曲名吻合。

    規則：藝人名稱與曲目名稱至少各有一方互相包含。
    """
    result_artists = [a["name"] for a in item["artists"]]
    result_title = item["name"]

    artist_ok = any(_is_match(artist, ra) for ra in result_artists)
    title_ok = _is_match(title, result_title)

    return artist_ok and title_ok


def search_track(sp: spotipy.Spotify, artist: str, title: str) -> str | None:
    """在 Spotify 搜尋曲目，回傳曲目 URI 或 None。

    搜尋策略：
    1. 精確搜尋：使用 track: 和 artist: 欄位限定
    2. 寬鬆搜尋：直接搜尋「藝人 曲名」
    兩種方式皆需通過藝人 + 曲名雙重驗證才視為配對成功。
    """
    search_artist = re.split(
        r"\s+(?:feat(?:uring)?|ft)\.?\s+", artist, maxsplit=1, flags=re.IGNORECASE,
    )[0]

    # 第一步：精確搜尋
    query = f"track:{title} artist:{search_artist}"
    results = sp.search(q=query, type="track", limit=5)
    for item in results["tracks"]["items"]:
        if _verify_result(item, artist, title):
            return item["uri"]

    # 第二步：寬鬆搜尋（不帶欄位限定）
    query = f"{search_artist} {title}"
    results = sp.search(q=query, type="track", limit=5)
    for item in results["tracks"]["items"]:
        if _verify_result(item, artist, title):
            return item["uri"]

    return None


# ── 播放清單管理 ──


def _get_all_playlist_tracks(sp: spotipy.Spotify, playlist_id: str) -> list[dict]:
    """取得播放清單中所有曲目，回傳 [{uri, added_at}, ...]。"""
    tracks: list[dict] = []
    results = sp.playlist_items(
        playlist_id,
        fields="items(track(uri),added_at),next",
    )
    while results:
        for item in results["items"]:
            if item.get("track") and item["track"].get("uri"):
                tracks.append({
                    "uri": item["track"]["uri"],
                    "added_at": item["added_at"],
                })
        if results.get("next"):
            results = sp.next(results)
        else:
            break
    return tracks


def _find_playlist(sp: spotipy.Spotify, name: str) -> str | None:
    """依名稱搜尋使用者播放清單，回傳 playlist ID 或 None。"""
    offset = 0
    while True:
        playlists = sp.current_user_playlists(limit=50, offset=offset)
        for pl in playlists["items"]:
            if pl["name"] == name:
                return pl["id"]
        if not playlists["next"]:
            break
        offset += 50
    return None


def get_or_create_playlist(
    sp: spotipy.Spotify, name: str | None = None, description: str | None = None
) -> str:
    """取得現有播放清單，或建立新的播放清單。回傳播放清單 ID。"""
    name = name or PLAYLIST_NAME
    description = description or PLAYLIST_DESCRIPTION
    user_id = sp.current_user()["id"]

    # 逐頁搜尋使用者現有的播放清單
    offset = 0
    while True:
        playlists = sp.current_user_playlists(limit=50, offset=offset)
        for pl in playlists["items"]:
            if pl["name"] == name:
                logger.info(f"找到現有播放清單：{name} ({pl['id']})")
                # 同步更新描述（確保描述始終為最新）
                sp.playlist_change_details(pl["id"], description=description)
                return pl["id"]
        if not playlists["next"]:
            break
        offset += 50

    # 未找到 → 建立新播放清單
    playlist = sp.user_playlist_create(
        user=user_id,
        name=name,
        public=True,
        description=description,
    )
    logger.info(f"已建立新播放清單：{name} ({playlist['id']})")
    return playlist["id"]


def add_tracks_to_playlist(sp: spotipy.Spotify, playlist_id: str, uris: list[str]) -> None:
    """批次加入曲目至播放清單（Spotify API 每次上限 100 首）。

    加入前先去重：DB 的去重鍵是 (artist, title)，不同來源對同一首歌的字串寫法
    可能不同，兩筆不同的 DB 紀錄仍可能指向同一個 Spotify URI。
    """
    if not uris:
        return

    existing = {t["uri"] for t in _get_all_playlist_tracks(sp, playlist_id)}
    new_uris = list(dict.fromkeys(u for u in uris if u not in existing))
    if not new_uris:
        logger.info("播放清單已包含所有曲目，無需加入")
        return

    for i in range(0, len(new_uris), 100):
        batch = new_uris[i : i + 100]
        sp.playlist_add_items(playlist_id, batch)
        logger.info(f"已加入 {len(batch)} 首曲目至播放清單")


def clear_playlist(sp: spotipy.Spotify, playlist_id: str) -> int:
    """清除播放清單中的所有曲目，回傳移除的曲目數。"""
    all_tracks = _get_all_playlist_tracks(sp, playlist_id)
    if not all_tracks:
        return 0

    uris = [t["uri"] for t in all_tracks]
    for i in range(0, len(uris), 100):
        sp.playlist_remove_all_occurrences_of_items(playlist_id, uris[i : i + 100])

    logger.info(f"已清除播放清單中 {len(uris)} 首曲目")
    return len(uris)


# ── All Time 累積歌單 ──


def _get_all_time_playlist(sp: spotipy.Spotify) -> str:
    """取得或建立 All Time 累積歌單，回傳 playlist ID。"""
    return get_or_create_playlist(
        sp,
        name=ALL_TIME_PLAYLIST_NAME,
        description=ALL_TIME_PLAYLIST_DESCRIPTION,
    )


def mirror_to_all_time(sp: spotipy.Spotify, uris: list[str]) -> int:
    """將曲目鏡射至只進不出的 All Time 累積歌單，回傳實際新增數。

    主歌單每季會被 archive_previous_quarters() 搬空、歷史散落在各季歸檔歌單中，
    這份則永不歸檔，是唯一一個能一眼看完所有蒐集結果的歌單。
    去重後才寫入，所以重複呼叫是安全的。
    """
    if not uris:
        return 0

    playlist_id = _get_all_time_playlist(sp)
    existing = {t["uri"] for t in _get_all_playlist_tracks(sp, playlist_id)}
    # dict.fromkeys 保序去重：backfill 會串接多個來源歌單，同一首歌可能重複出現，
    # 只比對 existing 擋不住批次內部的重複
    new_uris = list(dict.fromkeys(u for u in uris if u not in existing))

    for i in range(0, len(new_uris), 100):
        sp.playlist_add_items(playlist_id, new_uris[i : i + 100])

    logger.info(f"All Time 累積歌單新增 {len(new_uris)} 首（送入 {len(uris)} 首）")
    return len(new_uris)


def backfill_all_time(sp: spotipy.Spotify) -> int:
    """把主歌單與所有季度歸檔歌單回填進 All Time 累積歌單，回傳新增數。

    一次性初始化用，但因為 mirror_to_all_time() 會去重，也可當作事後修復工具
    （例如某週鏡射失敗時補回漏掉的曲目）。
    """
    uris: list[str] = []

    main_id = get_or_create_playlist(sp)
    uris.extend(t["uri"] for t in _get_all_playlist_tracks(sp, main_id))
    logger.info(f"主歌單：{len(uris)} 首")

    offset = 0
    while True:
        playlists = sp.current_user_playlists(limit=50, offset=offset)
        for pl in playlists["items"]:
            # 排除 All Time 自己，否則會把目標歌單當成來源
            if (
                pl["name"].startswith("Critics' Picks —")
                and pl["name"] not in (PLAYLIST_NAME, ALL_TIME_PLAYLIST_NAME)
            ):
                archived = [t["uri"] for t in _get_all_playlist_tracks(sp, pl["id"])]
                uris.extend(archived)
                logger.info(f"歸檔歌單 {pl['name']}：{len(archived)} 首")
        if not playlists.get("next"):
            break
        offset += 50

    return mirror_to_all_time(sp, uris)


# ── 播放清單合併與季度歸檔 ──


def migrate_old_playlist(
    sp: spotipy.Spotify,
    new_playlist_id: str,
    old_name: str = "Daily Music Picks",
) -> None:
    """將舊播放清單的曲目合併至新清單，然後移除舊清單。"""
    old_id = _find_playlist(sp, old_name)
    if not old_id:
        return

    logger.info(f"找到舊播放清單 '{old_name}'，開始合併...")

    old_tracks = _get_all_playlist_tracks(sp, old_id)
    if not old_tracks:
        sp.current_user_unfollow_playlist(old_id)
        logger.info("舊播放清單為空，已移除")
        return

    # 取得新清單現有曲目以避免重複
    new_tracks = _get_all_playlist_tracks(sp, new_playlist_id)
    existing_uris = {t["uri"] for t in new_tracks}

    new_uris = [t["uri"] for t in old_tracks if t["uri"] not in existing_uris]
    for i in range(0, len(new_uris), 100):
        sp.playlist_add_items(new_playlist_id, new_uris[i : i + 100])

    sp.current_user_unfollow_playlist(old_id)
    logger.info(f"已合併 {len(new_uris)} 首曲目至新清單，舊播放清單已移除")


def archive_previous_quarters(sp: spotipy.Spotify, playlist_id: str) -> None:
    """將主播放清單中屬於前季的曲目歸檔至季度播放清單。

    依據 Spotify 記錄的 added_at 時間判斷曲目所屬季度，
    非當季的曲目會移至「Critics' Picks — YYYY QN」歸檔清單。
    """
    all_tracks = _get_all_playlist_tracks(sp, playlist_id)
    if not all_tracks:
        return

    now = datetime.now(timezone.utc)
    current_year = now.year
    current_q = get_quarter(now.month)

    # 依季度分組（僅選出不屬於當季的曲目）
    to_archive: dict[tuple[int, int], list[str]] = {}
    for t in all_tracks:
        added = datetime.fromisoformat(t["added_at"].replace("Z", "+00:00"))
        y = added.year
        q = get_quarter(added.month)
        if (y, q) != (current_year, current_q):
            to_archive.setdefault((y, q), []).append(t["uri"])

    if not to_archive:
        return

    user_id = sp.current_user()["id"]
    uris_to_remove: list[str] = []

    for (year, quarter), uris in sorted(to_archive.items()):
        archive_name = f"Critics' Picks — {year} Q{quarter}"
        archive_id = _find_playlist(sp, archive_name)

        if not archive_id:
            desc = f"Critics' Picks {year} 年第 {quarter} 季歸檔｜由 Music Collector 自動管理"
            playlist = sp.user_playlist_create(
                user=user_id,
                name=archive_name,
                public=True,
                description=desc,
            )
            archive_id = playlist["id"]
            logger.info(f"已建立歸檔播放清單：{archive_name}")

        # 避免重複加入
        existing_uris = {t["uri"] for t in _get_all_playlist_tracks(sp, archive_id)}
        new_uris = [u for u in uris if u not in existing_uris]

        for i in range(0, len(new_uris), 100):
            sp.playlist_add_items(archive_id, new_uris[i : i + 100])

        uris_to_remove.extend(uris)
        logger.info(f"已歸檔 {len(new_uris)} 首至 {archive_name}")

    # 從主播放清單移除已歸檔曲目
    for i in range(0, len(uris_to_remove), 100):
        sp.playlist_remove_all_occurrences_of_items(
            playlist_id, uris_to_remove[i : i + 100],
        )

    logger.info(f"已從主播放清單移除 {len(uris_to_remove)} 首過季曲目")
