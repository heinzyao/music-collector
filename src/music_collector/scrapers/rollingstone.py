"""Rolling Stone 擷取器（HTML，二階段）。

來源：rollingstone.com — 全球知名音樂與流行文化雜誌。
擷取方式：
  1. 掃描音樂新聞與特輯索引頁，篩選推薦性質的文章
     （如「Best New Songs」、「Song You Need to Know」、「Premiere」）
  2. 進入推薦文章頁面，從 h2/h3 標題中提取曲目
過濾年度回顧清單與純新聞報導。
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

# 推薦類文章關鍵詞 — 標題或 URL 須包含至少一個
_RECOMMEND_KEYWORDS = [
    "best new song", "best new track", "best new music",
    "song you need", "songs you need",
    "song of the week", "track of the week",
    "need to hear", "need to know",
    "songs this week", "tracks this week",
    "songs right now", "tracks right now",
    "premiere", "first listen",
]

# 年度回顧 / 排行榜關鍵詞
_RECAP_KEYWORDS = [
    "best of", "best songs of", "best albums of", "best tracks of",
    "top 100", "top 50", "top 25", "top 10",
    "ranked", "ranking", "of the year", "of the decade",
    "year in review", "year-end", "greatest", "all time",
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
            tracks.extend(self._scan_index(soup))

            if len(tracks) >= MAX_TRACKS_PER_SOURCE:
                break

        logger.info(f"Rolling Stone：找到 {len(tracks[:MAX_TRACKS_PER_SOURCE])} 首曲目")
        return tracks[:MAX_TRACKS_PER_SOURCE]

    def _scan_index(self, soup: BeautifulSoup) -> list[Track]:
        """掃描索引頁，僅篩選推薦類文章並提取曲目。"""
        tracks: list[Track] = []
        seen_urls: set[str] = set()

        for link in soup.select("h2 a, h3 a, .c-card__title a"):
            text = self.clean_text(link.get_text())
            href = link.get("href", "")
            text_lower = text.lower()
            href_lower = href.lower()

            # 跳過年度回顧
            if any(kw in text_lower for kw in _RECAP_KEYWORDS):
                continue

            # 必須是推薦類文章（標題或 URL 包含推薦關鍵詞）
            if not any(kw in text_lower or kw.replace(" ", "-") in href_lower
                       for kw in _RECOMMEND_KEYWORDS):
                continue

            # 嘗試直接從標題提取單首推薦
            parsed = self._parse_recommendation_headline(text)
            if parsed:
                tracks.append(Track(artist=parsed[0], title=parsed[1], source=self.name))
                continue

            # 彙整類文章（如「Best New Songs This Week」）→ 進入文章提取
            if href.startswith("/"):
                href = "https://www.rollingstone.com" + href
            if not href.startswith("http") or href in seen_urls:
                continue
            seen_urls.add(href)

            try:
                article_tracks = self._parse_article(href)
                tracks.extend(article_tracks)
            except Exception as e:
                logger.warning(f"Rolling Stone：文章解析失敗 {href}: {e}")

        return tracks

    def _parse_article(self, url: str) -> list[Track]:
        """解析推薦文章內容，從段落中提取曲目。

        Rolling Stone 推薦清單的曲目格式為段落內的 'Artist, "Title"'，
        而非使用 h2/h3 標題。
        """
        resp = self._get(url)
        soup = BeautifulSoup(resp.text, "lxml")
        tracks: list[Track] = []
        seen: set[tuple[str, str]] = set()

        for p in soup.select("p.paragraph, article p"):
            text = self.clean_text(p.get_text())
            # 匹配「Artist, "Title"」或「Artist, 'Title'」
            for m in re.finditer(
                r"([A-Z][\w\s.'\-]+?),\s*[\u201c\"']+(.+?)[\u201d\"']+",
                text,
            ):
                artist = m.group(1).strip()
                title = m.group(2).strip()
                key = (artist.lower(), title.lower())
                if len(artist) > 1 and len(title) > 1 and key not in seen:
                    seen.add(key)
                    tracks.append(Track(artist=artist, title=title, source=self.name))

        return tracks

    def _parse_recommendation_headline(self, text: str) -> tuple[str, str] | None:
        """從推薦標題中提取單首曲目。

        格式：
        - "Song You Need to Know: Artist, 'Title'"
        - "First Listen: Artist — 'Title'"
        - "Artist Premieres New Song 'Title'"
        """
        # 「Song You Need to Know: Artist — 'Title'」
        m = re.match(
            r".*(?:Need to (?:Know|Hear)|Song of the Week|Track of the Week)\s*:\s*"
            r"(.+?)\s*[,–—-]\s*['\u2018\u201c\"]+(.+?)['\u2019\u201d\"]+",
            text,
            re.IGNORECASE,
        )
        if m:
            return m.group(1).strip(), m.group(2).strip()

        # 「First Listen: Artist — 'Title'」
        m = re.match(
            r".*(?:First Listen|Premiere)\s*:\s*"
            r"(.+?)\s*[,–—-]\s*['\u2018\u201c\"]+(.+?)['\u2019\u201d\"]+",
            text,
            re.IGNORECASE,
        )
        if m:
            return m.group(1).strip(), m.group(2).strip()

        # 「Artist Premieres/Debuts/Unveils New Song 'Title'」
        m = re.match(
            r"^(.+?)\s+(?:Premieres?|Debuts?|Unveils?)"
            r".*?['\u2018\u201c\"]+(.+?)['\u2019\u201d\"]+",
            text,
        )
        if m:
            artist = m.group(1).strip().rstrip("'s").rstrip("\u2019s")
            title = m.group(2).strip()
            if len(artist) > 1 and len(title) > 1:
                return artist, title

        return None
