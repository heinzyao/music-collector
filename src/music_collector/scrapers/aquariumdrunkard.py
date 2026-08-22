"""Aquarium Drunkard 擷取器（RSS）。

來源：aquariumdrunkard.com — 迷幻、民謠、爵士取向的獨立音樂推薦。
擷取方式：解析 RSS feed。
標題格式：「Artist :: Title」（固定分隔符號，解析無歧義）。

這個站把專欄文章混在同一個 feed 裡（影評 Videodrome、專訪、Podcast、每月選輯），
且大量收錄現場與 archival 錄音 —— 這些在 Spotify 幾乎搜不到，寧可過濾掉。
"""

import logging

import feedparser

from .base import BaseScraper, Track
from ..config import MAX_TRACKS_PER_SOURCE

logger = logging.getLogger(__name__)

FEED_URL = "https://aquariumdrunkard.com/feed/"

SEPARATOR = " :: "

# 專欄名稱會出現在藝人的位置
SKIP_COLUMNS = {
    "videodrome",
    "transmissions",
    "radio free aquarium drunkard",
    "black rock",
}

# 專欄自帶的 tag
SKIP_TAGS = {"videodrome", "the ad interview", "podcast"}


class AquariumDrunkardScraper(BaseScraper):
    name = "Aquarium Drunkard"

    def fetch_tracks(self) -> list[Track]:
        tracks: list[Track] = []
        feed = feedparser.parse(FEED_URL)

        if feed.bozo and not feed.entries:
            logger.warning("Aquarium Drunkard RSS feed 解析失敗")
            return tracks

        for entry in feed.entries[:MAX_TRACKS_PER_SOURCE]:
            title_text = self.clean_text(entry.get("title", ""))
            categories = [c.get("term", "") for c in entry.get("tags", [])]

            if any(c.lower() in SKIP_TAGS for c in categories):
                continue

            parsed = self._parse(title_text, categories)
            if parsed:
                artist, title = parsed
                tracks.append(Track(artist=artist, title=title, source=self.name))

        logger.info(f"Aquarium Drunkard：找到 {len(tracks)} 首曲目")
        return tracks

    @staticmethod
    def _parse(text: str, categories: list[str]) -> tuple[str, str] | None:
        """解析「Artist :: Title」，過濾專欄與現場／archival 錄音。"""
        if SEPARATOR not in text:
            return None

        artist, title = (p.strip() for p in text.split(SEPARATOR, 1))
        if not artist or not title:
            return None

        if artist.lower() in SKIP_COLUMNS:
            return None

        # 括號幾乎只出現在現場與 archival 錄音的場地／年份註記
        if "(" in title:
            return None

        # 藝人名必須對得上 tag。專欄名不會被 tag 成藝人，因此這條規則
        # 連未來新增的專欄也擋得住，不必逐一維護黑名單
        lower = artist.lower()
        if not any(c and lower.startswith(c.lower()) for c in categories):
            return None

        return artist, title
