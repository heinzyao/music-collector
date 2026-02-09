"""The Quietus 擷取器（RSS）。

來源：thequietus.com — 英國獨立音樂與實驗音樂評論。
擷取方式：解析 RSS feed，過濾 Reviews 分類。
標題格式：「Artist – Album」（樂評標題）。
"""

import logging

import feedparser

from .base import BaseScraper, Track
from ..config import MAX_TRACKS_PER_SOURCE

logger = logging.getLogger(__name__)

FEED_URL = "https://thequietus.com/feed"


class TheQuietusScraper(BaseScraper):
    name = "The Quietus"

    def fetch_tracks(self) -> list[Track]:
        tracks: list[Track] = []
        feed = feedparser.parse(FEED_URL)

        if feed.bozo and not feed.entries:
            logger.warning("The Quietus RSS feed 解析失敗")
            return tracks

        for entry in feed.entries[:MAX_TRACKS_PER_SOURCE]:
            title_text = entry.get("title", "")
            categories = [c.get("term", "").lower() for c in entry.get("tags", [])]

            # 過濾樂評相關文章
            is_review = any(
                kw in cat
                for cat in categories
                for kw in ["reviews", "review", "albums", "tracks", "music"]
            )
            if not is_review:
                continue

            # 跳過非藝人標題（如「The Quietus Guide to...」、「X Best Albums of...」）
            lower = title_text.lower()
            if any(
                skip in lower
                for skip in [
                    "guide to",
                    "best albums",
                    "best tracks",
                    "interview",
                    "in photos",
                    "playlist",
                ]
            ):
                continue

            # The Quietus 標題通常為「Artist – Album」格式
            parsed = self.parse_artist_title(title_text)
            if parsed:
                artist, title = parsed
                tracks.append(Track(artist=artist, title=title, source=self.name))

        logger.info(f"The Quietus：找到 {len(tracks)} 首曲目")
        return tracks
