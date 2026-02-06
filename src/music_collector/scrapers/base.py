import logging
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass

import httpx

from ..config import REQUEST_TIMEOUT, USER_AGENT

logger = logging.getLogger(__name__)


@dataclass
class Track:
    artist: str
    title: str
    source: str


class BaseScraper(ABC):
    name: str = "base"

    @abstractmethod
    def fetch_tracks(self) -> list[Track]:
        ...

    def _get(self, url: str) -> httpx.Response:
        headers = {"User-Agent": USER_AGENT}
        resp = httpx.get(url, headers=headers, timeout=REQUEST_TIMEOUT, follow_redirects=True)
        resp.raise_for_status()
        return resp

    @staticmethod
    def parse_artist_title(text: str) -> tuple[str, str] | None:
        """Parse 'Artist - Title' or 'Artist – Title' or 'Artist: Title' strings."""
        text = text.strip()
        for sep in [" – ", " - ", " — ", ": "]:
            if sep in text:
                parts = text.split(sep, 1)
                artist = parts[0].strip().strip('"').strip("'")
                title = parts[1].strip().strip('"').strip("'")
                if artist and title:
                    return artist, title
        return None

    @staticmethod
    def clean_text(text: str) -> str:
        """Remove extra whitespace, HTML entities, etc."""
        text = re.sub(r"\s+", " ", text).strip()
        return text
