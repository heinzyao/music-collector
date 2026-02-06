import logging

import feedparser

from .base import BaseScraper, Track
from ..config import MAX_TRACKS_PER_SOURCE

logger = logging.getLogger(__name__)

FEED_URL = "https://pitchfork.com/feed/feed-album-reviews/rss"


class PitchforkScraper(BaseScraper):
    name = "Pitchfork"

    def fetch_tracks(self) -> list[Track]:
        tracks: list[Track] = []
        feed = feedparser.parse(FEED_URL)

        if feed.bozo and not feed.entries:
            logger.warning("Pitchfork RSS feed failed to parse")
            return tracks

        for entry in feed.entries[:MAX_TRACKS_PER_SOURCE]:
            title_text = entry.get("title", "")
            parsed = self.parse_artist_title(title_text)
            if parsed:
                artist, title = parsed
                tracks.append(Track(artist=artist, title=title, source=self.name))
            else:
                # Try to extract from summary/tags for "Best New Track" entries
                tags = [t.get("term", "") for t in entry.get("tags", [])]
                if any("best new" in t.lower() for t in tags):
                    # Title format is often just "Album Name" — use author field
                    author = entry.get("author", "")
                    if author and title_text:
                        tracks.append(Track(artist=author, title=title_text, source=self.name))

        logger.info(f"Pitchfork: found {len(tracks)} tracks")
        return tracks
