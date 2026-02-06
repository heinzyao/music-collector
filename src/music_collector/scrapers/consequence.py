import logging
import re

from bs4 import BeautifulSoup

from .base import BaseScraper, Track
from ..config import MAX_TRACKS_PER_SOURCE

logger = logging.getLogger(__name__)

URL = "https://consequence.net/category/cos-exclusive-features/top-song-of-the-week/"


class ConsequenceScraper(BaseScraper):
    name = "Consequence"

    def fetch_tracks(self) -> list[Track]:
        tracks: list[Track] = []
        resp = self._get(URL)
        soup = BeautifulSoup(resp.text, "lxml")

        # WordPress archive: headings are in h3>a or h2>a
        # Format: "Heavy Song of the Week: Artist's 'Song' Does Something"
        # or "Staff Picks: Best Songs of the Week ..."
        for heading in soup.select("h2 a, h3 a")[:MAX_TRACKS_PER_SOURCE]:
            text = self.clean_text(heading.get_text())
            parsed = self._parse_consequence_title(text)
            if parsed:
                artist, title = parsed
                tracks.append(Track(artist=artist, title=title, source=self.name))

        logger.info(f"Consequence: found {len(tracks)} tracks")
        return tracks

    @staticmethod
    def _parse_consequence_title(text: str) -> tuple[str, str] | None:
        """Parse Consequence article titles.

        Formats:
          - "Heavy Song of the Week: Artist's 'Song Title' Description"
          - "Song of the Week: Artist – Song Title"
          - "Staff Picks: Best Songs of the Week ..." (skip these)
        """
        # Skip roundup articles
        if "staff picks" in text.lower() or "best songs of the week" in text.lower():
            return None

        # Strip prefix like "Heavy Song of the Week:" or "Song of the Week:"
        colon_idx = text.find(":")
        if colon_idx != -1:
            text = text[colon_idx + 1:].strip()

        # Try to find song in quotes
        m = re.search(r"['\u2018\u2019\u201c\u201d\"]+(.+?)['\u2018\u2019\u201c\u201d\"]+", text)
        if m:
            title = m.group(1).strip()
            # Artist is before the quoted song
            prefix = text[:m.start()].strip()
            # Remove possessive 's from end
            artist = re.sub(r"['`\u2019]s?\s*$", "", prefix).strip()
            if artist and title:
                return artist, title

        # Fallback: Artist – Title format
        for sep in [" – ", " - ", " — "]:
            if sep in text:
                parts = text.split(sep, 1)
                return parts[0].strip(), parts[1].strip()

        return None
