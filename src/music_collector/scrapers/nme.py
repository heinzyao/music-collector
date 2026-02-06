import logging
import re

from bs4 import BeautifulSoup

from .base import BaseScraper, Track
from ..config import MAX_TRACKS_PER_SOURCE

logger = logging.getLogger(__name__)

URL = "https://www.nme.com/features/music-features"


class NMEScraper(BaseScraper):
    name = "NME"

    def fetch_tracks(self) -> list[Track]:
        tracks: list[Track] = []
        resp = self._get(URL)
        soup = BeautifulSoup(resp.text, "lxml")

        # Find "best new tracks" roundup articles using .entry-title
        for heading in soup.select(".entry-title, h3.entry-title")[:100]:
            link = heading.find("a")
            if not link:
                continue
            text = self.clean_text(heading.get_text()).lower()
            href = link.get("href", "")

            if not any(kw in text or kw in href for kw in [
                "best new", "essential new", "tracks to listen", "tracks you need",
                "best-new", "tracks-listen",
            ]):
                continue

            if href.startswith("/"):
                href = "https://www.nme.com" + href
            if not href.startswith("http"):
                continue

            try:
                article_tracks = self._parse_article(href)
                tracks.extend(article_tracks[:MAX_TRACKS_PER_SOURCE])
            except Exception as e:
                logger.warning(f"NME: failed to parse article {href}: {e}")

            if tracks:
                break  # Most recent article is enough

        logger.info(f"NME: found {len(tracks)} tracks")
        return tracks

    def _parse_article(self, url: str) -> list[Track]:
        resp = self._get(url)
        soup = BeautifulSoup(resp.text, "lxml")
        tracks: list[Track] = []

        # NME lists tracks in h2/h3 within the article, format: "Artist – 'Song Title'"
        for heading in soup.select("h2, h3"):
            text = self.clean_text(heading.get_text())

            # Try quoted song with artist prefix
            m = re.match(r"^(.+?)\s*[–—-]\s*['\u2018\u201c\"](.+?)['\u2019\u201d\"]", text)
            if m:
                tracks.append(Track(artist=m.group(1).strip(), title=m.group(2).strip(), source=self.name))
                continue

            # Standard "Artist – Title" format
            parsed = self.parse_artist_title(text)
            if parsed:
                artist, title = parsed
                # Skip section headers and non-track headings
                if len(artist) > 3 and len(title) > 1:
                    tracks.append(Track(artist=artist, title=title, source=self.name))

        return tracks
