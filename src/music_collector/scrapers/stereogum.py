import logging
import re

import feedparser

from .base import BaseScraper, Track
from ..config import MAX_TRACKS_PER_SOURCE

logger = logging.getLogger(__name__)

FEED_URL = "https://www.stereogum.com/feed/"


class StereogumScraper(BaseScraper):
    name = "Stereogum"

    def fetch_tracks(self) -> list[Track]:
        tracks: list[Track] = []
        feed = feedparser.parse(FEED_URL)

        if feed.bozo and not feed.entries:
            logger.warning("Stereogum RSS feed failed to parse")
            return tracks

        for entry in feed.entries[:MAX_TRACKS_PER_SOURCE]:
            title_text = entry.get("title", "")
            categories = [c.get("term", "").lower() for c in entry.get("tags", [])]

            # Filter for track-related posts
            is_track = any(
                kw in cat
                for cat in categories
                for kw in ["track", "song", "single", "video", "new music"]
            )
            if not is_track:
                continue

            parsed = self._parse_stereogum_title(title_text)
            if parsed:
                artist, title = parsed
                tracks.append(Track(artist=artist, title=title, source=self.name))

        logger.info(f"Stereogum: found {len(tracks)} tracks")
        return tracks

    @staticmethod
    def _parse_stereogum_title(text: str) -> tuple[str, str] | None:
        """Parse Stereogum RSS titles.

        Formats:
          - 'Artist — "Song Title"'
          - 'Artist Announces Album Name — Hear "Song Title"'
          - 'Artist — "Song1" & "Song2"'
        """
        # Direct format: Artist — "Song"
        m = re.match(r'^(.+?)\s*[—–-]\s*["\u201c](.+?)["\u201d]', text)
        if m:
            return m.group(1).strip(), m.group(2).strip()

        # Announcement format: "... Hear "Song Title""
        m = re.search(r'[Hh]ear\s+["\u201c](.+?)["\u201d]', text)
        if m:
            # Artist is everything before "Announce" or first verb
            artist_m = re.match(r'^(.+?)\s+(?:Announce|Share|Release|Debut|Drop|Unveil|Return)', text)
            if artist_m:
                return artist_m.group(1).strip(), m.group(1).strip()

        # Title track format: "... Hear The Title Track"
        if "Hear The Title Track" in text or "Hear the Title Track" in text:
            # Album name is usually after "Album" or before " — "
            artist_m = re.match(r'^(.+?)\s+(?:Announce|Share)', text)
            album_m = re.search(r'(?:Album|EP|LP|Project)\s+(.+?)\s*[—–-]', text)
            if artist_m and album_m:
                return artist_m.group(1).strip(), album_m.group(1).strip()

        return None
