"""Pitchfork 擷取器（HTML）。

來源：pitchfork.com — 全球最具影響力的獨立音樂評論網站。
擷取方式：解析「Best New Tracks」頁面的 HTML，提取曲目標題與藝人名。
頁面結構：
  - 每首曲目包含在 div.SummaryItemWrapper 中
  - 曲名在 h3.summary-item__hed 中（帶有 typographic 引號需去除）
  - 藝人名在 div.summary-item__sub-hed 中
"""

import logging
import re

from bs4 import BeautifulSoup

from .base import BaseScraper, Track
from ..config import MAX_TRACKS_PER_SOURCE

logger = logging.getLogger(__name__)

URL = "https://pitchfork.com/reviews/best/tracks/"


class PitchforkScraper(BaseScraper):
    name = "Pitchfork"

    def fetch_tracks(self) -> list[Track]:
        tracks: list[Track] = []

        try:
            resp = self._get(URL)
        except Exception as e:
            logger.warning(f"Pitchfork：頁面請求失敗: {e}")
            return tracks

        soup = BeautifulSoup(resp.text, "lxml")

        # 主要策略：從 SummaryItemWrapper 容器提取
        # 注意：只匹配 class 以 "SummaryItemWrapper" 開頭的 div，
        # 避免匹配到子元素（如 SummaryItemContent, SummaryItemAssetContainer）
        items = soup.select("div[class*='SummaryItemWrapper']")

        if items:
            for item in items[:MAX_TRACKS_PER_SOURCE]:
                # 曲名：h3.summary-item__hed
                title_el = item.select_one("h3[class*='summary-item__hed']")
                # 藝人：div.summary-item__sub-hed
                artist_el = item.select_one("div[class*='summary-item__sub-hed']")

                if not title_el or not artist_el:
                    continue

                title = self._clean_title(self.clean_text(title_el.get_text()))
                artist = self.clean_text(artist_el.get_text())

                if artist and title:
                    tracks.append(Track(artist=artist, title=title, source=self.name))
        else:
            # 備選策略：嘗試從所有 h3 + 相鄰元素提取
            logger.debug("Pitchfork：未找到 SummaryItemWrapper，嘗試備選策略")
            for h3 in soup.select("h3")[:MAX_TRACKS_PER_SOURCE]:
                text = self.clean_text(h3.get_text())
                cleaned = self._clean_title(text)
                if not cleaned:
                    continue

                # 嘗試從相鄰元素取得藝人名
                parent = h3.parent
                if parent:
                    sub = parent.select_one("div, span")
                    if sub and sub != h3:
                        artist = self.clean_text(sub.get_text())
                        if artist and cleaned:
                            tracks.append(
                                Track(artist=artist, title=cleaned, source=self.name)
                            )

        # 去重（以防 HTML 結構變動導致重複）
        seen = set()
        unique = []
        for t in tracks:
            key = (t.artist.lower(), t.title.lower())
            if key not in seen:
                seen.add(key)
                unique.append(t)

        logger.info(f"Pitchfork：找到 {len(unique)} 首曲目")
        return unique

    @staticmethod
    def _clean_title(text: str) -> str:
        """移除曲名周圍的 typographic 引號與一般引號。

        Pitchfork 的曲名格式：「"Hard"」或「"Sé Miimii" [ft. DJ Skycee]」
        需要移除包裹曲名的引號，但保留 [ft. ...] 等附加資訊。
        """
        # 移除開頭的引號
        text = re.sub(r"^[\u2018\u2019\u201c\u201d\'\"]+", "", text)
        # 移除結尾的引號
        text = re.sub(r"[\u2018\u2019\u201c\u201d\'\"]+$", "", text)
        # 移除曲名部分結尾的引號（在 [ft.] 等附加資訊前）
        text = re.sub(r"[\u2018\u2019\u201c\u201d\'\"]+(\s*\[)", r"\1", text)
        return text.strip()
