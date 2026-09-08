"""Bandcamp Daily 擷取器（RSS）。

來源：daily.bandcamp.com — Bandcamp 官方編輯推薦。
擷取方式：解析 RSS feed，只取分類正好是「Album of the Day」的項目。

feed 裡三分之二是月度榜單（Best Metal…）、專欄（Lists、Features、Scene
Report）與合輯（Essential Releases），標題是散文句子，硬解析只會生出
「Learning by Doing — Making Music as Melaina Kol」這種假曲目。
Album of the Day 則一律是「Artist, "Album"」，分類本身就是最準的過濾條件。
"""

import logging
import re

import feedparser

from .base import BaseScraper, Track
from ..config import MAX_TRACKS_PER_SOURCE

logger = logging.getLogger(__name__)

FEED_URL = "https://daily.bandcamp.com/feed"

# 「Artist, "Album"」。引號成對匹配，否則專輯名裡的撇號會提早收尾
# （Various Artists, "Can't Stop It! II…" 會被截成 "Can"）
_TITLE_RE = re.compile(
    r"^(?P<artist>.+?),\s*"
    r"(?:\u201c(?P<curly>[^\u201d]+)\u201d"
    r"|\u2018(?P<single>[^\u2019]+)\u2019"
    r"|\"(?P<straight>[^\"]+)\")"
)


class BandcampDailyScraper(BaseScraper):
    name = "Bandcamp Daily"

    def fetch_tracks(self) -> list[Track]:
        tracks: list[Track] = []
        feed = feedparser.parse(FEED_URL)

        if feed.bozo and not feed.entries:
            logger.warning("Bandcamp Daily RSS feed 解析失敗")
            return tracks

        for entry in feed.entries[:MAX_TRACKS_PER_SOURCE]:
            title_text = entry.get("title", "")
            categories = [c.get("term", "").lower() for c in entry.get("tags", [])]

            if "album of the day" not in categories:
                continue

            parsed = self._parse_bandcamp_title(title_text)
            if parsed:
                artist, title = parsed
                tracks.append(Track(artist=artist, title=title, source=self.name))

        logger.info(f"Bandcamp Daily：找到 {len(tracks)} 首曲目")
        return tracks

    @staticmethod
    def _parse_bandcamp_title(text: str) -> tuple[str, str] | None:
        """解析「Artist, "Album"」標題，提取藝人與專輯名。

        artist 用非貪婪並錨定句首，讓含逗號的團名完整保留
        （"Henry Threadgill, Vijay Iyer & Dafnis Prieto"）。
        沒有備選格式：Album of the Day 一律是這個寫法，多加一條 dash 備選
        只會把偶爾混入的散文標題切成假曲目。
        """
        m = _TITLE_RE.match(text)
        if not m:
            return None

        artist = m.group("artist").strip()
        title = (m.group("curly") or m.group("single") or m.group("straight")).strip()
        return (artist, title) if artist and title else None
