import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# Spotify
SPOTIFY_CLIENT_ID = os.environ.get("SPOTIFY_CLIENT_ID", "")
SPOTIFY_CLIENT_SECRET = os.environ.get("SPOTIFY_CLIENT_SECRET", "")
SPOTIFY_REDIRECT_URI = os.environ.get("SPOTIFY_REDIRECT_URI", "http://127.0.0.1:8888/callback")
PLAYLIST_NAME = os.environ.get("PLAYLIST_NAME", "Daily Music Picks")

# Paths
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DATA_DIR = PROJECT_ROOT / "data"
DB_PATH = DATA_DIR / "tracks.db"
SPOTIFY_CACHE_PATH = PROJECT_ROOT / ".spotify_cache"

# Scraping
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)
REQUEST_TIMEOUT = 30
MAX_TRACKS_PER_SOURCE = 50
