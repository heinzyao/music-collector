"""One-time Spotify auth helper.

Opens browser for Spotify OAuth, catches the callback on a local server,
and caches the token so the main script can run unattended.
"""

import sys
import threading
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

SCOPE = "playlist-modify-public playlist-modify-private"

# Will be set by the callback handler
auth_code = None


class CallbackHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        global auth_code
        query = parse_qs(urlparse(self.path).query)
        auth_code = query.get("code", [None])[0]
        error = query.get("error", [None])[0]

        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        if auth_code:
            self.wfile.write(b"<h1>Authorization successful!</h1><p>You can close this tab.</p>")
        else:
            self.wfile.write(f"<h1>Authorization failed</h1><p>{error}</p>".encode())

    def log_message(self, format, *args):
        pass  # Suppress server logs


def main():
    if not SPOTIFY_CLIENT_ID or not SPOTIFY_CLIENT_SECRET:
        print("ERROR: Set SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET in .env")
        sys.exit(1)

    auth_manager = SpotifyOAuth(
        client_id=SPOTIFY_CLIENT_ID,
        client_secret=SPOTIFY_CLIENT_SECRET,
        redirect_uri=SPOTIFY_REDIRECT_URI,
        scope=SCOPE,
        cache_path=str(SPOTIFY_CACHE_PATH),
        open_browser=False,
    )

    # Check if already cached
    token_info = auth_manager.cache_handler.get_cached_token()
    if token_info and not auth_manager.is_token_expired(token_info):
        print("Already authenticated! Token is cached and valid.")
        sp = spotipy.Spotify(auth_manager=auth_manager)
        user = sp.current_user()
        print(f"Logged in as: {user['display_name']} ({user['id']})")
        return

    # Parse port from redirect URI
    parsed = urlparse(SPOTIFY_REDIRECT_URI)
    port = parsed.port or 8888

    # Start local server to catch callback
    server = HTTPServer(("127.0.0.1", port), CallbackHandler)
    server.timeout = 120  # 2 min per request

    auth_url = auth_manager.get_authorize_url()
    print(f"\nOpening browser for Spotify authorization...")
    print(f"(If it doesn't open, visit: {auth_url})\n")
    print(f"Waiting for authorization on port {port}...")
    webbrowser.open(auth_url)

    # Wait for one request (the callback)
    server.handle_request()
    server.server_close()

    if not auth_code:
        print("ERROR: No authorization code received.")
        sys.exit(1)

    print("Authorization code received! Exchanging for token...")
    token_info = auth_manager.get_access_token(auth_code, as_dict=True)

    sp = spotipy.Spotify(auth_manager=auth_manager)
    user = sp.current_user()
    print(f"\nSuccess! Logged in as: {user['display_name']} ({user['id']})")
    print(f"Token cached at: {SPOTIFY_CACHE_PATH}")


if __name__ == "__main__":
    main()
