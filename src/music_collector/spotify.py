"""Spotify 整合模組：認證、搜尋曲目、管理播放清單。

使用 spotipy 函式庫透過 OAuth 2.0 Authorization Code Flow 連線。
首次執行需瀏覽器授權，之後 Token 自動從快取更新。
"""

import logging

import spotipy
from spotipy.oauth2 import SpotifyOAuth

from .config import (
    PLAYLIST_NAME,
    SPOTIFY_CACHE_PATH,
    SPOTIFY_CLIENT_ID,
    SPOTIFY_CLIENT_SECRET,
    SPOTIFY_REDIRECT_URI,
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


def search_track(sp: spotipy.Spotify, artist: str, title: str) -> str | None:
    """在 Spotify 搜尋曲目，回傳曲目 URI 或 None。

    搜尋策略：
    1. 精確搜尋：使用 track: 和 artist: 欄位限定
    2. 寬鬆搜尋：直接搜尋「藝人 曲名」，並驗證結果相似度
    """
    # 第一步：精確搜尋
    query = f"track:{title} artist:{artist}"
    results = sp.search(q=query, type="track", limit=5)
    items = results["tracks"]["items"]

    if items:
        return items[0]["uri"]

    # 第二步：寬鬆搜尋（不帶欄位限定）
    query = f"{artist} {title}"
    results = sp.search(q=query, type="track", limit=5)
    items = results["tracks"]["items"]

    if items:
        # 驗證搜尋結果是否大致吻合
        top = items[0]
        result_artist = top["artists"][0]["name"].lower()
        result_title = top["name"].lower()
        if artist.lower() in result_artist or result_artist in artist.lower():
            return top["uri"]
        if title.lower() in result_title or result_title in title.lower():
            return top["uri"]

    return None


def get_or_create_playlist(sp: spotipy.Spotify, name: str | None = None) -> str:
    """取得現有播放清單，或建立新的播放清單。回傳播放清單 ID。"""
    name = name or PLAYLIST_NAME
    user_id = sp.current_user()["id"]

    # 逐頁搜尋使用者現有的播放清單
    offset = 0
    while True:
        playlists = sp.current_user_playlists(limit=50, offset=offset)
        for pl in playlists["items"]:
            if pl["name"] == name:
                logger.info(f"找到現有播放清單：{name} ({pl['id']})")
                return pl["id"]
        if not playlists["next"]:
            break
        offset += 50

    # 未找到 → 建立新播放清單
    playlist = sp.user_playlist_create(
        user=user_id,
        name=name,
        public=True,
        description="自動策展：每日精選音樂評論推薦曲目",
    )
    logger.info(f"已建立新播放清單：{name} ({playlist['id']})")
    return playlist["id"]


def add_tracks_to_playlist(sp: spotipy.Spotify, playlist_id: str, uris: list[str]) -> None:
    """批次加入曲目至播放清單（Spotify API 每次上限 100 首）。"""
    for i in range(0, len(uris), 100):
        batch = uris[i : i + 100]
        sp.playlist_add_items(playlist_id, batch)
        logger.info(f"已加入 {len(batch)} 首曲目至播放清單")
