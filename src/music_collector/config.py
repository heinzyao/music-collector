"""設定模組：從 .env 載入環境變數，定義全域常數。"""

import os
from pathlib import Path

from dotenv import load_dotenv

# 載入 .env 檔案中的環境變數
load_dotenv()

# ── Spotify API 憑證 ──
SPOTIFY_CLIENT_ID = os.environ.get("SPOTIFY_CLIENT_ID", "")
SPOTIFY_CLIENT_SECRET = os.environ.get("SPOTIFY_CLIENT_SECRET", "")
SPOTIFY_REDIRECT_URI = os.environ.get("SPOTIFY_REDIRECT_URI", "http://127.0.0.1:8888/callback")
PLAYLIST_NAME = os.environ.get("PLAYLIST_NAME", "Daily Music Picks")

# ── 檔案路徑 ──
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent  # 專案根目錄
DATA_DIR = PROJECT_ROOT / "data"                              # 資料存放目錄
DB_PATH = DATA_DIR / "tracks.db"                              # SQLite 資料庫路徑
SPOTIFY_CACHE_PATH = PROJECT_ROOT / ".spotify_cache"          # Spotify OAuth Token 快取

# ── 網頁擷取設定 ──
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)
REQUEST_TIMEOUT = 30          # HTTP 請求逾時秒數
MAX_TRACKS_PER_SOURCE = 50    # 每個來源最多擷取的曲目數
