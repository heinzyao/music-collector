"""Stereogum 擷取器（RSS）。

來源：stereogum.com — 獨立音樂與另類音樂新聞網站。
擷取方式：解析 RSS feed，過濾 track/single/new music 相關分類。
標題格式多變：
  - 直接格式：「Artist — "Song Title"」
  - 公告格式：「Artist Announces Album — Hear "Song Title"」
  - 同名曲格式：「... Hear The Title Track」
"""

import logging
import re

import feedparser

from .base import BaseScraper, Track
from ..config import MAX_TRACKS_PER_SOURCE

logger = logging.getLogger(__name__)

FEED_URL = "https://www.stereogum.com/feed/"


class StereogumScraper(BaseScraper):
    name = "Stereogum"

    def fetch_tracks(self) -> list[Track]:
        tracks: list[Track] = []
        feed = feedparser.parse(FEED_URL)

        if feed.bozo and not feed.entries:
            logger.warning("Stereogum RSS feed 解析失敗")
            return tracks

        for entry in feed.entries[:MAX_TRACKS_PER_SOURCE]:
            title_text = entry.get("title", "")
            categories = [c.get("term", "").lower() for c in entry.get("tags", [])]

            # 過濾與曲目相關的文章（依分類標籤判斷）
            is_track = any(
                kw in cat
                for cat in categories
                for kw in ["track", "song", "single", "video", "new music"]
            )
            if not is_track:
                continue

            parsed = self._parse_stereogum_title(title_text)
            if parsed:
                artist, title = parsed
                tracks.append(Track(artist=artist, title=title, source=self.name))

        logger.info(f"Stereogum：找到 {len(tracks)} 首曲目")
        return tracks

    @staticmethod
    def _parse_stereogum_title(text: str) -> tuple[str, str] | None:
        """解析 Stereogum RSS 標題，提取藝人與曲名。"""
        # 格式一：「Artist — "Song"」（直接格式）
        m = re.match(r'^(.+?)\s*[—–-]\s*["\u201c](.+?)["\u201d]', text)
        if m:
            return m.group(1).strip(), m.group(2).strip()

        # 格式二：「... Hear "Song Title"」（公告格式）
        m = re.search(r'[Hh]ear\s+["\u201c](.+?)["\u201d]', text)
        if m:
            # 藝人名在 Announce/Share 等動詞之前
            artist_m = re.match(r'^(.+?)\s+(?:Announce|Share|Release|Debut|Drop|Unveil|Return)', text)
            if artist_m:
                return artist_m.group(1).strip(), m.group(1).strip()

        # 格式三：「... Hear The Title Track」（專輯同名曲）
        if "Hear The Title Track" in text or "Hear the Title Track" in text:
            artist_m = re.match(r'^(.+?)\s+(?:Announce|Share)', text)
            album_m = re.search(r'(?:Album|EP|LP|Project)\s+(.+?)\s*[—–-]', text)
            if artist_m and album_m:
                return artist_m.group(1).strip(), album_m.group(1).strip()

        return None
