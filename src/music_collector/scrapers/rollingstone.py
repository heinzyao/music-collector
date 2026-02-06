import logging
from datetime import datetime

from bs4 import BeautifulSoup

from .base import BaseScraper, Track
from ..config import MAX_TRACKS_PER_SOURCE

logger = logging.getLogger(__name__)

URL = "https://www.rollingstone.com/music/music-lists/"


class RollingStoneScraper(BaseScraper):
    name = "Rolling Stone"

    def fetch_tracks(self) -> list[Track]:
        tracks: list[Track] = []
        resp = self._get(URL)
        soup = BeautifulSoup(resp.text, "lxml")

        current_year = datetime.now().year

        # Find links to "best songs" lists from current or recent year
        best_songs_url = None
        for link in soup.select("a[href]")[:200]:
            href = link.get("href", "")
            text = link.get_text().lower()
            if ("best-songs" in href or "best songs" in text) and (
                str(current_year) in href or str(current_year - 1) in href
            ):
                best_songs_url = href
                break

        if not best_songs_url:
            logger.info("Rolling Stone: no current best-songs list found")
            return tracks

        if best_songs_url.startswith("/"):
            best_songs_url = "https://www.rollingstone.com" + best_songs_url

        try:
            resp = self._get(best_songs_url)
        except Exception as e:
            logger.warning(f"Rolling Stone: failed to fetch list page: {e}")
            return tracks

        soup = BeautifulSoup(resp.text, "lxml")

        # List items are typically in headings or structured list entries
        for heading in soup.select("h2, h3, .c-gallery-vertical-album__title"):
            text = self.clean_text(heading.get_text())
            parsed = self.parse_artist_title(text)
            if parsed:
                artist, title = parsed
                tracks.append(Track(artist=artist, title=title, source=self.name))

        logger.info(f"Rolling Stone: found {len(tracks[:MAX_TRACKS_PER_SOURCE])} tracks")
        return tracks[:MAX_TRACKS_PER_SOURCE]
