import logging
import re

from bs4 import BeautifulSoup

from .base import BaseScraper, Track
from ..config import MAX_TRACKS_PER_SOURCE

logger = logging.getLogger(__name__)

# Complex / Pigeons & Planes — try multiple URL patterns
URLS = [
    "https://www.complex.com/music",
    "https://www.complex.com/tag/best-new-music",
    "https://www.complex.com/pigeons-and-planes",
]


class ComplexScraper(BaseScraper):
    name = "Complex"

    def fetch_tracks(self) -> list[Track]:
        tracks: list[Track] = []

        for url in URLS:
            try:
                resp = self._get(url)
            except Exception:
                continue

            soup = BeautifulSoup(resp.text, "lxml")

            for heading in soup.select("h2 a, h3 a, article a, .post-title a")[:MAX_TRACKS_PER_SOURCE]:
                text = self.clean_text(heading.get_text())
                if not text or len(text) < 5:
                    continue

                # Strip common prefixes
                for prefix in [
                    "Best New Music This Week:",
                    "Best New Music:",
                    "New Music:",
                    "Premiere:",
                    "Stream:",
                    "Listen:",
                ]:
                    if text.lower().startswith(prefix.lower()):
                        text = text[len(prefix):].strip()

                # Try to find quoted song title
                m = re.search(r"['\u2018\u201c\"]+(.+?)['\u2019\u201d\"]+", text)
                if m:
                    title = m.group(1).strip()
                    artist = text[:m.start()].strip().rstrip("'s").rstrip(",").strip()
                    if artist and title:
                        tracks.append(Track(artist=artist, title=title, source=self.name))
                        continue

                parsed = self.parse_artist_title(text)
                if parsed:
                    artist, title = parsed
                    tracks.append(Track(artist=artist, title=title, source=self.name))

            if tracks:
                break

        logger.info(f"Complex: found {len(tracks)} tracks")
        return tracks
