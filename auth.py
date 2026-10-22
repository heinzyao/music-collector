"""Spotify OAuth 一次性授權工具。

首次使用時執行此腳本：
    PYTHONPATH=src uv run python auth.py

spotipy 會開瀏覽器到授權頁，並在 SPOTIFY_REDIRECT_URI 的本機埠接回呼；
Token 快取至 .spotify_cache（可用環境變數 SPOTIFY_CACHE_PATH 覆寫），後續執行主程式時自動更新。
"""

import sys

sys.path.insert(0, "src")
from music_collector.config import (
    SPOTIFY_CLIENT_ID,
    SPOTIFY_CLIENT_SECRET,
    SPOTIFY_REDIRECT_URI,
    SPOTIFY_CACHE_PATH,
)
# 從主程式取用同一份 scope，兩邊各寫一份會漂移（授權到的權限不夠主程式用）
from music_collector.spotify import SCOPE

import spotipy
from spotipy.oauth2 import SpotifyOAuth


def main():
    if not SPOTIFY_CLIENT_ID or not SPOTIFY_CLIENT_SECRET:
        print("錯誤：請在 .env 中設定 SPOTIFY_CLIENT_ID 和 SPOTIFY_CLIENT_SECRET")
        sys.exit(1)

    auth_manager = SpotifyOAuth(
        client_id=SPOTIFY_CLIENT_ID,
        client_secret=SPOTIFY_CLIENT_SECRET,
        redirect_uri=SPOTIFY_REDIRECT_URI,
        scope=SCOPE,
        cache_path=str(SPOTIFY_CACHE_PATH),
        # 強制顯示帳號選擇畫面。否則瀏覽器已登入哪個帳號就直接發那個帳號的 token，
        # 換帳號時會神不知鬼不覺地授權到舊帳號。
        show_dialog=True,
    )

    # 快取有效就直接用；否則 spotipy 開瀏覽器並在本機埠等回呼
    user = spotipy.Spotify(auth_manager=auth_manager).current_user()
    print(f"\n已登入：{user['display_name']} ({user['id']})")
    print(f"Token 已快取至：{SPOTIFY_CACHE_PATH}")


if __name__ == "__main__":
    main()
