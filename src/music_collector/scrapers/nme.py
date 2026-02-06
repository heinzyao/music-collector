"""NME 擷取器（HTML，二階段）。

來源：nme.com — 英國歷史最悠久的音樂週刊之一。
擷取方式：
  1. 第一階段：掃描 /features/music-features 索引頁，找到最新的
     「best new tracks」彙整文章連結
  2. 第二階段：進入該文章頁面，從 h2/h3 標題中提取各曲目
標題格式：「Artist – 'Song Title'」或「Artist – Song Title」
"""

import logging
import re

from bs4 import BeautifulSoup

from .base import BaseScraper, Track
from ..config import MAX_TRACKS_PER_SOURCE

logger = logging.getLogger(__name__)

# NME 音樂特輯索引頁
URL = "https://www.nme.com/features/music-features"


class NMEScraper(BaseScraper):
    name = "NME"

    def fetch_tracks(self) -> list[Track]:
        tracks: list[Track] = []
        resp = self._get(URL)
        soup = BeautifulSoup(resp.text, "lxml")

        # 第一階段：從索引頁找到「best new tracks」彙整文章
        for heading in soup.select(".entry-title, h3.entry-title")[:100]:
            link = heading.find("a")
            if not link:
                continue
            text = self.clean_text(heading.get_text()).lower()
            href = link.get("href", "")

            # 過濾關鍵字：只要含有 "best new" 或 "tracks to listen" 的文章
            if not any(kw in text or kw in href for kw in [
                "best new", "essential new", "tracks to listen", "tracks you need",
                "best-new", "tracks-listen",
            ]):
                continue

            if href.startswith("/"):
                href = "https://www.nme.com" + href
            if not href.startswith("http"):
                continue

            # 第二階段：解析文章內容提取曲目
            try:
                article_tracks = self._parse_article(href)
                tracks.extend(article_tracks[:MAX_TRACKS_PER_SOURCE])
            except Exception as e:
                logger.warning(f"NME：文章解析失敗 {href}: {e}")

            if tracks:
                break  # 只需最新一篇文章

        logger.info(f"NME：找到 {len(tracks)} 首曲目")
        return tracks

    def _parse_article(self, url: str) -> list[Track]:
        """解析 NME 文章頁面，從標題中提取曲目。"""
        resp = self._get(url)
        soup = BeautifulSoup(resp.text, "lxml")
        tracks: list[Track] = []

        for heading in soup.select("h2, h3"):
            text = self.clean_text(heading.get_text())

            # 嘗試帶引號的格式：「Artist – 'Song Title'」
            m = re.match(r"^(.+?)\s*[–—-]\s*['\u2018\u201c\"](.+?)['\u2019\u201d\"]", text)
            if m:
                tracks.append(Track(artist=m.group(1).strip(), title=m.group(2).strip(), source=self.name))
                continue

            # 備選：標準「Artist – Title」格式
            parsed = self.parse_artist_title(text)
            if parsed:
                artist, title = parsed
                # 排除過短的標題（可能是章節標題而非曲目）
                if len(artist) > 3 and len(title) > 1:
                    tracks.append(Track(artist=artist, title=title, source=self.name))

        return tracks
