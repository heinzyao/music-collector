import logging

from bs4 import BeautifulSoup

from .base import BaseScraper, Track
from ..config import MAX_TRACKS_PER_SOURCE

logger = logging.getLogger(__name__)

# /tracks redirects to /reviews/singles
URLS = [
    "https://ra.co/reviews/singles",
    "https://ra.co/tracks",
]


class ResidentAdvisorScraper(BaseScraper):
    name = "Resident Advisor"

    def fetch_tracks(self) -> list[Track]:
        tracks: list[Track] = []

        for url in URLS:
            try:
                resp = self._get(url)
            except Exception:
                continue

            soup = BeautifulSoup(resp.text, "lxml")

            # RA is a React app — much of the content may not be in initial HTML.
            # Try various selectors for whatever server-renders.
            for item in soup.select(
                "li a, article a, [class*='track'] a, [class*='Track'] a, h3 a"
            )[:MAX_TRACKS_PER_SOURCE]:
                text = self.clean_text(item.get_text())
                if not text or len(text) < 5:
                    continue

                parsed = self.parse_artist_title(text)
                if parsed:
                    artist, title = parsed
                    tracks.append(Track(artist=artist, title=title, source=self.name))

            if tracks:
                break

        # Deduplicate
        seen = set()
        unique = []
        for t in tracks:
            key = (t.artist.lower(), t.title.lower())
            if key not in seen:
                seen.add(key)
                unique.append(t)

        logger.info(f"Resident Advisor: found {len(unique)} tracks")
        return unique
