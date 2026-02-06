"""Spotify OAuth 一次性授權工具。

首次使用時執行此腳本：
    PYTHONPATH=src uv run python auth.py

流程：
1. 在本機 8888 埠啟動 HTTP 伺服器
2. 開啟瀏覽器前往 Spotify 授權頁面
3. 使用者授權後，瀏覽器重新導向至本機，伺服器自動接收授權碼
4. 將 Token 快取至 .spotify_cache，後續執行主程式時自動更新
"""

import sys
import webbrowser
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

sys.path.insert(0, "src")
from music_collector.config import (
    SPOTIFY_CLIENT_ID,
    SPOTIFY_CLIENT_SECRET,
    SPOTIFY_REDIRECT_URI,
    SPOTIFY_CACHE_PATH,
)

import spotipy
from spotipy.oauth2 import SpotifyOAuth

# 播放清單讀寫權限
SCOPE = "playlist-modify-public playlist-modify-private"

# 由回呼處理器設定
auth_code = None


class CallbackHandler(BaseHTTPRequestHandler):
    """處理 Spotify OAuth 回呼的 HTTP 請求處理器。"""

    def do_GET(self):
        global auth_code
        query = parse_qs(urlparse(self.path).query)
        auth_code = query.get("code", [None])[0]
        error = query.get("error", [None])[0]

        # 回應瀏覽器
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        if auth_code:
            self.wfile.write(b"<h1>Authorization successful!</h1><p>You can close this tab.</p>")
        else:
            self.wfile.write(f"<h1>Authorization failed</h1><p>{error}</p>".encode())

    def log_message(self, format, *args):
        pass  # 隱藏伺服器日誌


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
        open_browser=False,  # 手動控制瀏覽器開啟時機
    )

    # 檢查是否已有有效的快取 Token
    token_info = auth_manager.cache_handler.get_cached_token()
    if token_info and not auth_manager.is_token_expired(token_info):
        print("已完成認證！Token 快取有效。")
        sp = spotipy.Spotify(auth_manager=auth_manager)
        user = sp.current_user()
        print(f"已登入：{user['display_name']} ({user['id']})")
        return

    # 從 redirect URI 解析埠號
    parsed = urlparse(SPOTIFY_REDIRECT_URI)
    port = parsed.port or 8888

    # 啟動本機 HTTP 伺服器接收回呼
    server = HTTPServer(("127.0.0.1", port), CallbackHandler)
    server.timeout = 120  # 等待授權的逾時秒數

    auth_url = auth_manager.get_authorize_url()
    print(f"\n正在開啟瀏覽器進行 Spotify 授權...")
    print(f"（若瀏覽器未自動開啟，請手動前往：{auth_url}）\n")
    print(f"等待授權中（埠 {port}）...")
    webbrowser.open(auth_url)

    # 等待一個 HTTP 請求（即 Spotify 的回呼）
    server.handle_request()
    server.server_close()

    if not auth_code:
        print("錯誤：未收到授權碼。")
        sys.exit(1)

    print("已收到授權碼！正在交換 Token...")
    token_info = auth_manager.get_access_token(auth_code, as_dict=True)

    sp = spotipy.Spotify(auth_manager=auth_manager)
    user = sp.current_user()
    print(f"\n成功！已登入：{user['display_name']} ({user['id']})")
    print(f"Token 已快取至：{SPOTIFY_CACHE_PATH}")


if __name__ == "__main__":
    main()
