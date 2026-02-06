"""Consequence of Sound 擷取器（HTML）。

來源：consequence.net — 美國綜合音樂媒體，涵蓋搖滾、金屬、嘻哈等類型。
擷取方式：解析「Top Song of the Week」分類頁面的文章標題。
標題格式：
  - 「Heavy Song of the Week: Artist's 'Song Title' Description」
  - 「Song of the Week: Artist – Song Title」
  - 「Staff Picks: Best Songs of the Week ...」（略過）
"""

import logging
import re

from bs4 import BeautifulSoup

from .base import BaseScraper, Track
from ..config import MAX_TRACKS_PER_SOURCE

logger = logging.getLogger(__name__)

# WordPress 分類頁面
URL = "https://consequence.net/category/cos-exclusive-features/top-song-of-the-week/"


class ConsequenceScraper(BaseScraper):
    name = "Consequence"

    def fetch_tracks(self) -> list[Track]:
        tracks: list[Track] = []
        resp = self._get(URL)
        soup = BeautifulSoup(resp.text, "lxml")

        # WordPress 分類彙整頁：標題在 h2>a 或 h3>a 中
        for heading in soup.select("h2 a, h3 a")[:MAX_TRACKS_PER_SOURCE]:
            text = self.clean_text(heading.get_text())
            parsed = self._parse_consequence_title(text)
            if parsed:
                artist, title = parsed
                tracks.append(Track(artist=artist, title=title, source=self.name))

        logger.info(f"Consequence：找到 {len(tracks)} 首曲目")
        return tracks

    @staticmethod
    def _parse_consequence_title(text: str) -> tuple[str, str] | None:
        """解析 Consequence 文章標題，提取藝人與曲名。"""
        # 略過彙整文章（非單曲推薦）
        if "staff picks" in text.lower() or "best songs of the week" in text.lower():
            return None

        # 移除前綴（如 "Heavy Song of the Week:"）
        colon_idx = text.find(":")
        if colon_idx != -1:
            text = text[colon_idx + 1:].strip()

        # 嘗試從引號中提取曲名
        m = re.search(r"['\u2018\u2019\u201c\u201d\"]+(.+?)['\u2018\u2019\u201c\u201d\"]+", text)
        if m:
            title = m.group(1).strip()
            prefix = text[:m.start()].strip()
            # 移除藝人名末尾的所有格 's
            artist = re.sub(r"['`\u2019]s?\s*$", "", prefix).strip()
            if artist and title:
                return artist, title

        # 備選：「Artist – Title」格式
        for sep in [" – ", " - ", " — "]:
            if sep in text:
                parts = text.split(sep, 1)
                return parts[0].strip(), parts[1].strip()

        return None
