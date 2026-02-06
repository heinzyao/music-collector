import logging
import re

from bs4 import BeautifulSoup

from .base import BaseScraper, Track
from ..config import MAX_TRACKS_PER_SOURCE

logger = logging.getLogger(__name__)

# Try multiple URL patterns — Slant may block some
URLS = [
    "https://www.slantmagazine.com/music/",
    "https://www.slantmagazine.com/category/music/",
]


class SlantScraper(BaseScraper):
    name = "Slant"

    def fetch_tracks(self) -> list[Track]:
        tracks: list[Track] = []

        for url in URLS:
            try:
                resp = self._get(url)
            except Exception:
                continue

            soup = BeautifulSoup(resp.text, "lxml")

            # Slant reviews: "Artist 'Album Title' Review: Description"
            for heading in soup.select("h2 a, h3 a, .post-title a, article h2, .entry-title a")[:MAX_TRACKS_PER_SOURCE]:
                text = self.clean_text(heading.get_text())

                # Skip non-music content
                if any(skip in text.lower() for skip in [
                    "best of", "worst of", "ranked", "interview", "the 25", "film", "tv",
                ]):
                    continue

                parsed = self._parse_slant_title(text)
                if parsed:
                    artist, title = parsed
                    tracks.append(Track(artist=artist, title=title, source=self.name))

            if tracks:
                break

        logger.info(f"Slant: found {len(tracks)} tracks")
        return tracks

    @staticmethod
    def _parse_slant_title(text: str) -> tuple[str, str] | None:
        """Parse Slant review titles.

        Format: "Artist 'Album/Track Title' Review: Description"
        or: "Artist 'Album/Track Title' Review — Description"
        """
        # Extract quoted album/track name
        m = re.search(r"['\u2018\u201c\"]+(.+?)['\u2019\u201d\"]+", text)
        if m:
            title = m.group(1).strip()
            artist = text[:m.start()].strip()
            if artist and title:
                return artist, title

        # Fallback: "Review: Artist, Title" or "Artist – Title"
        if text.lower().startswith("review:"):
            text = text[7:].strip()

        for sep in [" – ", " - ", " — "]:
            if sep in text:
                parts = text.split(sep, 1)
                return parts[0].strip(), parts[1].strip()

        return None
