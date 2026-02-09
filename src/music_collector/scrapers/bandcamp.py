"""Bandcamp Daily 擷取器（RSS）。

來源：daily.bandcamp.com — Bandcamp 官方編輯推薦。
擷取方式：解析 RSS feed，過濾「Album of the Day」分類。
標題格式多變：
  - 「Artist, "Album"」（Album of the Day）
  - 「Artist, "Album Title"」
  - 「Essential Releases, Feb 6」（合輯推薦，跳過）
"""

import logging
import re

import feedparser

from .base import BaseScraper, Track
from ..config import MAX_TRACKS_PER_SOURCE

logger = logging.getLogger(__name__)

FEED_URL = "https://daily.bandcamp.com/feed"


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

            # 過濾「Album of the Day」與「Best of」等推薦類別
            is_recommendation = any(
                kw in cat
                for cat in categories
                for kw in ["album of the day", "best of", "features"]
            )
            if not is_recommendation:
                continue

            # 跳過合輯推薦（如「Essential Releases, Feb 6」）
            if title_text.lower().startswith("essential releases"):
                continue
            if title_text.lower().startswith("the best "):
                continue

            parsed = self._parse_bandcamp_title(title_text)
            if parsed:
                artist, title = parsed
                tracks.append(Track(artist=artist, title=title, source=self.name))

        logger.info(f"Bandcamp Daily：找到 {len(tracks)} 首曲目")
        return tracks

    @staticmethod
    def _parse_bandcamp_title(text: str) -> tuple[str, str] | None:
        """解析 Bandcamp Daily 標題，提取藝人與專輯名。

        常見格式：
          - 「Artist, "Album Title"」
          - 「Artist, 'Album Title'」
        """
        # 格式一：逗號分隔 + 引號包裹的專輯名
        m = re.match(
            r'^(.+?),\s*["\u201c\u2018\']+(.+?)["\u201d\u2019\']+',
            text,
        )
        if m:
            artist = m.group(1).strip()
            title = m.group(2).strip()
            if artist and title:
                return artist, title

        # 格式二：標準「Artist – Title」格式（備選）
        result = BaseScraper.parse_artist_title(text)
        if result:
            return result

        return None
