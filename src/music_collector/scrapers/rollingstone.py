"""Rolling Stone 擷取器（HTML，二階段）。

來源：rollingstone.com — 全球知名音樂與流行文化雜誌。
擷取方式：掃描音樂新聞與音樂特輯索引頁，從近期文章標題中提取曲目。
過濾年度回顧清單（"best of"、"ranked"、"top 100" 等）。
"""

import logging
import re

from bs4 import BeautifulSoup

from .base import BaseScraper, Track
from ..config import MAX_TRACKS_PER_SOURCE

logger = logging.getLogger(__name__)

# 音樂新聞與特輯索引頁
URLS = [
    "https://www.rollingstone.com/music/music-news/",
    "https://www.rollingstone.com/music/music-features/",
]

# 年度回顧 / 排行榜關鍵詞（小寫比對）
_RECAP_KEYWORDS = [
    "best of", "best songs", "best albums", "best tracks",
    "top 100", "top 50", "top 25", "top 10",
    "ranked", "ranking", "of the year", "of the decade",
    "year in review", "year-end", "greatest",
]


class RollingStoneScraper(BaseScraper):
    name = "Rolling Stone"

    def fetch_tracks(self) -> list[Track]:
        tracks: list[Track] = []

        for url in URLS:
            try:
                resp = self._get(url)
            except Exception as e:
                logger.warning(f"Rolling Stone：索引頁擷取失敗 {url}: {e}")
                continue

            soup = BeautifulSoup(resp.text, "lxml")
            tracks.extend(self._extract_from_index(soup))

            if len(tracks) >= MAX_TRACKS_PER_SOURCE:
                break

        logger.info(f"Rolling Stone：找到 {len(tracks[:MAX_TRACKS_PER_SOURCE])} 首曲目")
        return tracks[:MAX_TRACKS_PER_SOURCE]

    def _extract_from_index(self, soup: BeautifulSoup) -> list[Track]:
        """從索引頁的文章標題中提取曲目。"""
        tracks: list[Track] = []

        for heading in soup.select("h2 a, h3 a, .c-card__title a, .l-section__content a h3"):
            text = self.clean_text(heading.get_text())
            text_lower = text.lower()

            # 跳過年度回顧 / 排行榜文章
            if any(kw in text_lower for kw in _RECAP_KEYWORDS):
                continue

            # 嘗試從標題中提取曲目
            parsed = self._parse_track_from_headline(text)
            if parsed:
                artist, title = parsed
                tracks.append(Track(artist=artist, title=title, source=self.name))

        return tracks

    def _parse_track_from_headline(self, text: str) -> tuple[str, str] | None:
        """從新聞標題中提取藝人與曲名。

        Rolling Stone 新聞標題常見格式：
        - "Artist Shares New Song 'Title'"
        - "Artist Releases 'Title'"
        - "Artist Drops New Single 'Title'"
        - "Watch Artist's New Video for 'Title'"
        - "Artist – 'Title'"
        - "Hear Artist's New Track 'Title'"
        """
        # 格式一：帶引號的曲名（最常見）
        # 匹配：Artist ... 'Title' / "Title"
        m = re.match(
            r"^(?:Watch |Hear |Listen to |Stream )?(.+?)\s+"
            r"(?:Shares?|Releases?|Drops?|Debuts?|Unveils?|Premieres?|Announces?)"
            r".*?['\u2018\u201c\"]+(.+?)['\u2019\u201d\"]+",
            text,
        )
        if m:
            artist = m.group(1).strip().rstrip("'s").rstrip("\u2019s")
            title = m.group(2).strip()
            if len(artist) > 1 and len(title) > 1:
                return artist, title

        # 格式二：Watch/Hear/Listen ... Artist's ... 'Title'
        m = re.match(
            r"^(?:Watch|Hear|Listen to|Stream)\s+(.+?)(?:'s|'s|\u2019s)\s+"
            r".*?['\u2018\u201c\"]+(.+?)['\u2019\u201d\"]+",
            text,
        )
        if m:
            artist = m.group(1).strip()
            title = m.group(2).strip()
            if len(artist) > 1 and len(title) > 1:
                return artist, title

        # 格式三：帶引號但無動詞的格式（如 "Artist 'Title'"）
        m = re.match(
            r"^(.+?)\s+['\u2018\u201c\"]+(.+?)['\u2019\u201d\"]+\s*$",
            text,
        )
        if m:
            artist = m.group(1).strip()
            title = m.group(2).strip()
            # 確認 artist 部分看起來像人名（不含太多單詞）
            if len(artist.split()) <= 4 and len(artist) > 1 and len(title) > 1:
                return artist, title

        return None
