import logging
import re

from bs4 import BeautifulSoup

from .base import BaseScraper, Track
from ..config import MAX_TRACKS_PER_SOURCE

logger = logging.getLogger(__name__)

# /new-music/song-of-the-day redirects to /tracks
URL = "https://www.thelineofbestfit.com/tracks"


class LineOfBestFitScraper(BaseScraper):
    name = "The Line of Best Fit"

    def fetch_tracks(self) -> list[Track]:
        tracks: list[Track] = []
        resp = self._get(URL)
        soup = BeautifulSoup(resp.text, "lxml")

        # Page has track links with titles like:
        #   "ARTIST NAME does something on genre 'Song Title'"
        # The song title is in single quotes at the end.
        for link in soup.select("a[href*='/tracks/']")[:MAX_TRACKS_PER_SOURCE]:
            text = self.clean_text(link.get_text())
            if not text or len(text) < 10:
                continue

            parsed = self._parse_lobf_title(text)
            if parsed:
                artist, title = parsed
                tracks.append(Track(artist=artist, title=title, source=self.name))

        # Deduplicate by (artist, title)
        seen = set()
        unique_tracks = []
        for t in tracks:
            key = (t.artist.lower(), t.title.lower())
            if key not in seen:
                seen.add(key)
                unique_tracks.append(t)

        logger.info(f"Line of Best Fit: found {len(unique_tracks)} tracks")
        return unique_tracks

    @staticmethod
    def _parse_lobf_title(text: str) -> tuple[str, str] | None:
        """Parse LOBF article titles.

        Format: "ARTIST NAME [verb phrase] 'Song Title'"
        The artist is the capitalized words at the start, song in quotes at end.
        """
        # Extract song title from single or double quotes
        m = re.search(r"['\u2018\u2019\u201c\u201d\"]+(.+?)['\u2018\u2019\u201c\u201d\"]+\s*$", text)
        if not m:
            return None
        title = m.group(1).strip()

        # Artist is typically ALL CAPS or Title Case at the beginning
        # Extract everything before common verb phrases
        prefix = text[:m.start()].strip()
        # Use a regex to find the first lowercase verb phrase — artist names are
        # typically capitalized/ALL CAPS, so the first lowercase word is the verb.
        # E.g. "MX LONELY numb the pain..." → artist="MX LONELY"
        #      "Sofia and the Antoinettes share..." → artist="Sofia and the Antoinettes"
        artist_m = re.match(
            r"^((?:[A-Z0-9][\w.]*(?:\s+(?:and|&|the|of|de|von|van|feat\.?|ft\.?)\s+)?)+)"
            r"(?:\s+[a-z])",
            prefix,
        )
        if artist_m:
            artist = artist_m.group(1).strip()
        else:
            # Fallback: try known verb list
            verbs = [
                " shares ", " share ", " unveils ", " unveil ", " releases ", " release ",
                " announces ", " announce ", " debuts ", " debut ", " delivers ", " deliver ",
                " drops ", " drop ", " returns ", " return ", " confronts ", " confront ",
                " explores ", " explore ", " channels ", " channel ", " captures ", " capture ",
                " embraces ", " embrace ", " numb ", " numbs ", " skewer ", " skewers ",
                " soars ", " soar ", " dives ", " dive ", " finds ", " find ",
                " reveals ", " reveal ", " offers ", " offer ", " brings ", " bring ",
                " opens ", " open ", " closes ", " close ", " paints ", " paint ",
                " wrestles ", " wrestle ", " navigates ", " navigate ", " plays ", " play ",
                " feels ", " feel ", " demands ", " demand ", " draws ", " draw ",
                " moves ", " move ", " gives ", " give ", " longs ", " long ",
                " marries ", " marry ", " steers ", " steer ", " wades ", " wade ",
                " resurrects ", " resurrect ", " sharpens ", " sharpen ",
                " does ", " do ", " is ", " are ", " has ", " have ", " gets ", " get ",
            ]
            artist = prefix
            for verb in verbs:
                idx = prefix.lower().find(verb)
                if idx != -1:
                    artist = prefix[:idx].strip()
                    break

        # Clean up artist name
        artist = artist.strip().strip(",").strip()
        if artist and title:
            return artist, title

        return None
