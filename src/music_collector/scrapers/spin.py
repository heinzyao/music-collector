import logging
from datetime import datetime

from bs4 import BeautifulSoup

from .base import BaseScraper, Track
from ..config import MAX_TRACKS_PER_SOURCE

logger = logging.getLogger(__name__)


class SpinScraper(BaseScraper):
    name = "SPIN"

    def fetch_tracks(self) -> list[Track]:
        tracks: list[Track] = []
        now = datetime.now()

        # Try current and previous month's "Now Hear This" roundup
        for month_offset in [0, 1]:
            month = now.month - month_offset
            year = now.year
            if month < 1:
                month += 12
                year -= 1

            month_str = datetime(year, month, 1).strftime("%b").lower()
            url = f"https://www.spin.com/{year}/{month:02d}/now-hear-this-{month_str}-{year}/"

            try:
                resp = self._get(url)
            except Exception:
                continue

            soup = BeautifulSoup(resp.text, "lxml")

            # Parse track listings from the article body
            for heading in soup.select("article h2, article h3, .entry-content h2, .entry-content h3"):
                text = self.clean_text(heading.get_text())
                parsed = self.parse_artist_title(text)
                if parsed:
                    artist, title = parsed
                    tracks.append(Track(artist=artist, title=title, source=self.name))

            # Also try list items and bold text patterns
            if not tracks:
                for item in soup.select(".entry-content p strong, .entry-content li"):
                    text = self.clean_text(item.get_text())
                    parsed = self.parse_artist_title(text)
                    if parsed:
                        artist, title = parsed
                        tracks.append(Track(artist=artist, title=title, source=self.name))

            if tracks:
                break

        logger.info(f"SPIN: found {len(tracks[:MAX_TRACKS_PER_SOURCE])} tracks")
        return tracks[:MAX_TRACKS_PER_SOURCE]
