"""Gorilla vs. Bear 擷取器（RSS）。

來源：gorillavsbear.net — 獨立音樂部落格，專注於新曲推薦。
擷取方式：解析 RSS feed，過濾 mp3/video/on-blast 分類。
標題格式：「Artist – Song Title」（與 Stereogum 相似，非常乾淨）。
"""

import logging

import feedparser

from .base import BaseScraper, Track
from ..config import MAX_TRACKS_PER_SOURCE

logger = logging.getLogger(__name__)

FEED_URL = "https://gorillavsbear.net/feed/"


class GorillaVsBearScraper(BaseScraper):
    name = "Gorilla vs. Bear"

    def fetch_tracks(self) -> list[Track]:
        tracks: list[Track] = []
        feed = feedparser.parse(FEED_URL)

        if feed.bozo and not feed.entries:
            logger.warning("Gorilla vs. Bear RSS feed 解析失敗")
            return tracks

        for entry in feed.entries[:MAX_TRACKS_PER_SOURCE]:
            title_text = entry.get("title", "")
            categories = [c.get("term", "").lower() for c in entry.get("tags", [])]

            # 過濾音樂推薦相關分類
            is_music = any(
                kw in cat
                for cat in categories
                for kw in ["mp3", "video", "on-blast", "music", "track", "single"]
            )
            if not is_music:
                continue

            # Gorilla vs. Bear 標題通常為「Artist – Title」格式
            parsed = self.parse_artist_title(title_text)
            if parsed:
                artist, title = parsed
                tracks.append(Track(artist=artist, title=title, source=self.name))

        logger.info(f"Gorilla vs. Bear：找到 {len(tracks)} 首曲目")
        return tracks
