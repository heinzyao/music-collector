import argparse
import logging
import sys

from .db import init_db, save_track, track_exists, get_recent_tracks
from .scrapers import ALL_SCRAPERS
from .scrapers.base import Track
from .spotify import add_tracks_to_playlist, get_or_create_playlist, get_spotify_client, search_track

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


def collect_tracks() -> list[Track]:
    """Run all scrapers and return new (unseen) tracks."""
    conn = init_db()
    new_tracks: list[Track] = []

    for scraper in ALL_SCRAPERS:
        try:
            tracks = scraper.fetch_tracks()
            for track in tracks:
                if not track_exists(conn, track.artist, track.title):
                    new_tracks.append(track)
        except Exception as e:
            logger.warning(f"{scraper.name} failed: {e}")

    conn.close()
    return new_tracks


def run(dry_run: bool = False) -> None:
    """Main pipeline: scrape → search Spotify → add to playlist."""
    logger.info("Starting music collection run...")

    new_tracks = collect_tracks()
    logger.info(f"Found {len(new_tracks)} new tracks across all sources")

    if not new_tracks:
        logger.info("No new tracks found. Done.")
        return

    if dry_run:
        logger.info("Dry run — tracks found but not added to Spotify:")
        for t in new_tracks:
            print(f"  [{t.source}] {t.artist} — {t.title}")
        return

    # Connect to Spotify
    sp = get_spotify_client()
    playlist_id = get_or_create_playlist(sp)

    conn = init_db()
    spotify_uris: list[str] = []
    not_found: list[Track] = []

    for track in new_tracks:
        try:
            uri = search_track(sp, track.artist, track.title)
            if uri:
                spotify_uris.append(uri)
                save_track(conn, track.artist, track.title, track.source, uri)
                logger.info(f"  Found: {track.artist} — {track.title}")
            else:
                not_found.append(track)
                save_track(conn, track.artist, track.title, track.source, None)
                logger.warning(f"  Not on Spotify: {track.artist} — {track.title}")
        except Exception as e:
            logger.warning(f"  Search failed for {track.artist} — {track.title}: {e}")

    conn.close()

    if spotify_uris:
        add_tracks_to_playlist(sp, playlist_id, spotify_uris)
        logger.info(f"Added {len(spotify_uris)} tracks to playlist")

    if not_found:
        logger.info(f"{len(not_found)} tracks not found on Spotify")

    logger.info("Done.")


def show_recent(days: int = 7) -> None:
    """Show recently collected tracks."""
    conn = init_db()
    tracks = get_recent_tracks(conn, days=days)
    conn.close()

    if not tracks:
        print(f"No tracks collected in the last {days} days.")
        return

    print(f"\nTracks collected in the last {days} days ({len(tracks)} total):\n")
    for t in tracks:
        status = "on Spotify" if t["spotify_uri"] else "not found"
        print(f"  [{t['source']}] {t['artist']} — {t['title']} ({status})")


def main() -> None:
    parser = argparse.ArgumentParser(description="Collect best tracks from music review sites")
    parser.add_argument("--dry-run", action="store_true", help="Scrape only, don't add to Spotify")
    parser.add_argument("--recent", type=int, metavar="DAYS", help="Show recently collected tracks")
    args = parser.parse_args()

    if args.recent is not None:
        show_recent(days=args.recent)
    else:
        run(dry_run=args.dry_run)
