"""Pitchfork 擷取器（RSS）。

來源：pitchfork.com — 全球最具影響力的獨立音樂評論網站。
擷取方式：解析專輯評論 RSS feed，過濾帶有 "Best New Track" 標籤的條目。
標題格式：「Artist: Album」或直接以 author 欄位作為藝人名。
"""

import logging

import feedparser

from .base import BaseScraper, Track
from ..config import MAX_TRACKS_PER_SOURCE

logger = logging.getLogger(__name__)

# Pitchfork 專輯評論 RSS feed
FEED_URL = "https://pitchfork.com/feed/feed-album-reviews/rss"


class PitchforkScraper(BaseScraper):
    name = "Pitchfork"

    def fetch_tracks(self) -> list[Track]:
        tracks: list[Track] = []
        feed = feedparser.parse(FEED_URL)

        if feed.bozo and not feed.entries:
            logger.warning("Pitchfork RSS feed 解析失敗")
            return tracks

        for entry in feed.entries[:MAX_TRACKS_PER_SOURCE]:
            title_text = entry.get("title", "")

            # 嘗試以「Artist – Title」格式解析
            parsed = self.parse_artist_title(title_text)
            if parsed:
                artist, title = parsed
                tracks.append(Track(artist=artist, title=title, source=self.name))
            else:
                # 備選策略：檢查是否帶有 "Best New Track" 標籤
                tags = [t.get("term", "") for t in entry.get("tags", [])]
                if any("best new" in t.lower() for t in tags):
                    # 此時標題通常只有專輯名，藝人名在 author 欄位
                    author = entry.get("author", "")
                    if author and title_text:
                        tracks.append(Track(artist=author, title=title_text, source=self.name))

        logger.info(f"Pitchfork：找到 {len(tracks)} 首曲目")
        return tracks
