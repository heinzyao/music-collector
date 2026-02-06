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

SCOPE = "playlist-modify-public playlist-modify-private"


def get_spotify_client() -> spotipy.Spotify:
    if not SPOTIFY_CLIENT_ID or not SPOTIFY_CLIENT_SECRET:
        raise RuntimeError(
            "Spotify credentials not set. "
            "Copy .env.example to .env and fill in SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET. "
            "Create an app at https://developer.spotify.com/dashboard"
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
    """Search for a track on Spotify. Returns the track URI or None."""
    # Try exact search first
    query = f"track:{title} artist:{artist}"
    results = sp.search(q=query, type="track", limit=5)
    items = results["tracks"]["items"]

    if items:
        return items[0]["uri"]

    # Fallback: looser search without field specifiers
    query = f"{artist} {title}"
    results = sp.search(q=query, type="track", limit=5)
    items = results["tracks"]["items"]

    if items:
        # Check that result roughly matches what we searched for
        top = items[0]
        result_artist = top["artists"][0]["name"].lower()
        result_title = top["name"].lower()
        if artist.lower() in result_artist or result_artist in artist.lower():
            return top["uri"]
        if title.lower() in result_title or result_title in title.lower():
            return top["uri"]

    return None


def get_or_create_playlist(sp: spotipy.Spotify, name: str | None = None) -> str:
    """Get existing playlist by name, or create a new one. Returns playlist ID."""
    name = name or PLAYLIST_NAME
    user_id = sp.current_user()["id"]

    # Check existing playlists
    offset = 0
    while True:
        playlists = sp.current_user_playlists(limit=50, offset=offset)
        for pl in playlists["items"]:
            if pl["name"] == name:
                logger.info(f"Found existing playlist: {name} ({pl['id']})")
                return pl["id"]
        if not playlists["next"]:
            break
        offset += 50

    # Create new playlist
    playlist = sp.user_playlist_create(
        user=user_id,
        name=name,
        public=True,
        description="Auto-curated daily picks from music review sites",
    )
    logger.info(f"Created new playlist: {name} ({playlist['id']})")
    return playlist["id"]


def add_tracks_to_playlist(sp: spotipy.Spotify, playlist_id: str, uris: list[str]) -> None:
    """Add tracks to playlist in batches of 100 (Spotify API limit)."""
    for i in range(0, len(uris), 100):
        batch = uris[i : i + 100]
        sp.playlist_add_items(playlist_id, batch)
        logger.info(f"Added batch of {len(batch)} tracks to playlist")
