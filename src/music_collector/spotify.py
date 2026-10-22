"""Spotify 整合模組：認證、搜尋曲目、管理播放清單、季度歸檔。

使用 spotipy 函式庫透過 OAuth 2.0 Authorization Code Flow 連線。
首次執行需瀏覽器授權，之後 Token 自動從快取更新。
"""

import logging
import re
from collections.abc import Iterator
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

# 播放清單讀寫權限。read-private 是必要的：get_or_create_playlist() 與
# backfill_all_time() 都靠 current_user_playlists() 找歌單，少了它會 403。
SCOPE = "playlist-modify-public playlist-modify-private playlist-read-private"


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


# 「樂團’s 團員」的寫法（Daughter’s Elena Tonra、Guided By Voices’ Doug Gillard）——
# Spotify 上的藝人是後半段那個人。要求剩下的部分至少兩個字：剝完只剩一個字
# （sachi’s mirror → mirror）太容易配到同名的別人。
_BAND_POSSESSIVE = re.compile(r"^.+[’\']s?\s+(?P<member>\S+\s+\S+.*)$")


def search_track(sp: spotipy.Spotify, artist: str, title: str) -> str | None:
    """在 Spotify 搜尋曲目，回傳曲目 URI 或 None。

    搜尋策略：
    1. 精確搜尋：使用 track: 和 artist: 欄位限定
    2. 寬鬆搜尋：直接搜尋「藝人 曲名」
    3. 剝掉樂團名的所有格前綴後重試
    三種方式皆需通過藝人 + 曲名雙重驗證才視為配對成功。

    第 3 步放在最後是刻意的：Melody’s Echo Chamber、L’Rain 這類真名帶撇號的
    藝人會在前兩步就命中，永遠走不到剝離那一步。
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

    # 第三步：剝掉樂團名的所有格前綴後重試
    m = _BAND_POSSESSIVE.match(search_artist)
    if m:
        member = m.group("member")
        results = sp.search(q=f"{member} {title}", type="track", limit=5)
        for item in results["tracks"]["items"]:
            if _verify_result(item, member, title):
                return item["uri"]

    return None


# ── 播放清單管理 ──


# ── 歌單項目 helper ──
# 2026 年後建立的 Developer app 被封掉 /playlists/{id}/tracks（spotipy 的
# playlist_items、playlist_add_items、playlist_remove_* 都走這條）與
# POST /users/{id}/playlists，只能走 /playlists/{id}/items 與 /me/playlists。
# 舊 app 兩條都能用，所以一律走新端點。讀寫歌單項目一律用以下 helper。


def _playlist_items(sp: spotipy.Spotify, playlist_id: str) -> Iterator[dict]:
    """逐頁產出歌單項目 {uri, id, added_at}（GET /items 一頁上限 50）。"""
    page = sp._get(f"playlists/{playlist_id}/items", limit=50)
    while page:
        for it in page["items"]:
            # 新 app 只有 item 鍵；舊 app 同時有 item 與 track
            track = it.get("item") or it.get("track")
            if track and track.get("uri"):
                yield {"uri": track["uri"], "id": track.get("id"), "added_at": it.get("added_at")}
        page = sp.next(page) if page.get("next") else None


def _add_items(sp: spotipy.Spotify, playlist_id: str, uris: list[str]) -> None:
    """依序加入曲目（每次 ≤100）。不去重 —— 呼叫端負責兩層去重。"""
    for i in range(0, len(uris), 100):
        sp._post(f"playlists/{playlist_id}/items", payload={"uris": uris[i : i + 100]})


def _remove_items(sp: spotipy.Spotify, playlist_id: str, uris: list[str]) -> None:
    """移除曲目的所有出現位置（每次 ≤100）。"""
    uris = list(dict.fromkeys(uris))
    for i in range(0, len(uris), 100):
        sp._delete(
            f"playlists/{playlist_id}/items",
            payload={"items": [{"uri": u} for u in uris[i : i + 100]]},
        )


def _create_playlist(sp: spotipy.Spotify, name: str, description: str, public: bool = True) -> str:
    """建立歌單（POST /me/playlists），回傳 ID。"""
    return sp._post(
        "me/playlists",
        payload={"name": name, "public": public, "description": description},
    )["id"]


def get_playlist_total(sp: spotipy.Spotify, playlist_id: str) -> int:
    """歌單曲目數。新 app 的歌單物件把 tracks 欄位改名為 items，兩者都接受。"""
    pl = sp.playlist(playlist_id, fields="items(total),tracks(total)")
    return (pl.get("items") or pl.get("tracks"))["total"]


def _get_all_playlist_tracks(sp: spotipy.Spotify, playlist_id: str) -> list[dict]:
    """取得播放清單中所有曲目，回傳 [{uri, id, added_at}, ...]。"""
    return list(_playlist_items(sp, playlist_id))


def _own_playlists(sp: spotipy.Spotify) -> Iterator[dict]:
    """逐頁產出使用者「自己擁有」的播放清單。

    current_user_playlists() 會一併回傳追蹤中的、別人擁有的歌單。只比對名稱的話，
    追蹤了同名歌單就會鎖定到別人的那一份，之後所有寫入都會失敗。
    """
    user_id = sp.current_user()["id"]
    offset = 0
    while True:
        page = sp.current_user_playlists(limit=50, offset=offset)
        for pl in page["items"]:
            if pl and pl["owner"]["id"] == user_id:  # 已刪除的歌單會是 null
                yield pl
        if not page.get("next"):
            break
        offset += 50


def _find_playlist(sp: spotipy.Spotify, name: str) -> str | None:
    """依名稱搜尋使用者自己的播放清單，回傳 playlist ID 或 None。"""
    return next((pl["id"] for pl in _own_playlists(sp) if pl["name"] == name), None)


def get_or_create_playlist(
    sp: spotipy.Spotify, name: str | None = None, description: str | None = None
) -> str:
    """取得現有播放清單，或建立新的播放清單。回傳播放清單 ID。"""
    name = name or PLAYLIST_NAME
    description = description or PLAYLIST_DESCRIPTION
    for pl in _own_playlists(sp):
        if pl["name"] == name:
            logger.info(f"找到現有播放清單：{name} ({pl['id']})")
            # 同步更新描述（確保描述始終為最新）
            sp.playlist_change_details(pl["id"], description=description)
            return pl["id"]

    # 未找到 → 建立新播放清單
    playlist_id = _create_playlist(sp, name, description)
    logger.info(f"已建立新播放清單：{name} ({playlist_id})")
    return playlist_id


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

    _add_items(sp, playlist_id, new_uris)
    logger.info(f"已加入 {len(new_uris)} 首曲目至播放清單")


def clear_playlist(sp: spotipy.Spotify, playlist_id: str) -> int:
    """清除播放清單中的所有曲目，回傳移除的曲目數。"""
    all_tracks = _get_all_playlist_tracks(sp, playlist_id)
    if not all_tracks:
        return 0

    uris = [t["uri"] for t in all_tracks]
    _remove_items(sp, playlist_id, uris)

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

    _add_items(sp, playlist_id, new_uris)

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

    for pl in _own_playlists(sp):
        # 排除 All Time 自己，否則會把目標歌單當成來源
        if (
            pl["name"].startswith("Critics' Picks —")
            and pl["name"] not in (PLAYLIST_NAME, ALL_TIME_PLAYLIST_NAME)
        ):
            archived = [t["uri"] for t in _get_all_playlist_tracks(sp, pl["id"])]
            uris.extend(archived)
            logger.info(f"歸檔歌單 {pl['name']}：{len(archived)} 首")

    return mirror_to_all_time(sp, uris)


# ── 季度歸檔 ──


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

    uris_to_remove: list[str] = []

    for (year, quarter), uris in sorted(to_archive.items()):
        archive_name = f"Critics' Picks — {year} Q{quarter}"
        archive_id = _find_playlist(sp, archive_name)

        if not archive_id:
            desc = f"Critics' Picks {year} 年第 {quarter} 季歸檔｜由 Music Collector 自動管理"
            archive_id = _create_playlist(sp, archive_name, desc)
            logger.info(f"已建立歸檔播放清單：{archive_name}")

        # 避免重複加入
        existing_uris = {t["uri"] for t in _get_all_playlist_tracks(sp, archive_id)}
        new_uris = list(dict.fromkeys(u for u in uris if u not in existing_uris))

        _add_items(sp, archive_id, new_uris)

        uris_to_remove.extend(uris)
        logger.info(f"已歸檔 {len(new_uris)} 首至 {archive_name}")

    # 從主播放清單移除已歸檔曲目
    _remove_items(sp, playlist_id, uris_to_remove)

    logger.info(f"已從主播放清單移除 {len(uris_to_remove)} 首過季曲目")
