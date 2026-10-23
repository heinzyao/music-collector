"""When We Dip 擷取器（RSS）。

來源：whenwedip.com — house／techno／melodic 等電子樂新曲評論與首播。
擷取方式：解析 RSS feed，只收 Reviews 與 Premieres 分類。
標題格式：「[Premiere: ]Artist verb … ‘Track’ on Label」，藝人名放在 category tag。

引號與 tag 比對沿用 SoulBounce（大小寫／重音／撇號摺疊）；另外 EP、VA、合輯常寫在
引號**後**（「‘Malone’ EP」），所以引號後緊接這些字也算專輯。
"""

import logging
import re

import feedparser

from .base import BaseScraper, Track
from .soulbounce import QUOTED, SoulBounceScraper
from ..config import MAX_TRACKS_PER_SOURCE

logger = logging.getLogger(__name__)

FEED_URL = "https://whenwedip.com/feed/"

KEEP_TAGS = {"reviews", "premieres"}
# 不含 mix：「a hypnotic mix of house on ‘Track’」很常見，DJ mix 已由 Podcasts 分類排除
ALBUM_BEFORE = re.compile(r"\b(album|lp|ep|mixtape|compilation|sampler)\b", re.I)
ALBUM_AFTER = re.compile(r"^\W*(ep|lp|album|va|sampler|compilation|mix|remixes|package)\b", re.I)
PREMIERE = re.compile(r"^premiere:\s*", re.I)


class WhenWeDipScraper(BaseScraper):
    name = "When We Dip"

    def fetch_tracks(self) -> list[Track]:
        tracks: list[Track] = []
        feed = feedparser.parse(FEED_URL)

        if feed.bozo and not feed.entries:
            logger.warning("When We Dip RSS feed 解析失敗")
            return tracks

        for entry in feed.entries[:MAX_TRACKS_PER_SOURCE]:
            categories = [c.get("term", "") for c in entry.get("tags", [])]
            # Events = 活動、Interviews = 專訪、Podcasts = DJ mix
            if not any(c.lower() in KEEP_TAGS for c in categories):
                continue

            text = PREMIERE.sub("", self.clean_text(entry.get("title", "")))
            title = self._extract_song_title(text)
            if not title:
                continue

            artist = SoulBounceScraper._match_artist_tag(text, categories)
            if artist:
                tracks.append(Track(artist=artist, title=title, source=self.name))

        logger.info(f"When We Dip：找到 {len(tracks)} 首曲目")
        return tracks

    @staticmethod
    def _extract_song_title(text: str) -> str | None:
        """取第一組不是 EP／專輯／合輯的引號內容。"""
        prev_end = 0
        for m in QUOTED.finditer(text):
            before = text[max(prev_end, m.start() - 30): m.start()]
            prev_end = m.end()
            if ALBUM_BEFORE.search(before) or ALBUM_AFTER.search(text[m.end():]):
                continue
            return m.group(1).strip()
        return None
