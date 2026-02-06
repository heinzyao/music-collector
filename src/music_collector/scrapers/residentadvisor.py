"""Resident Advisor 擷取器（HTML）。

來源：ra.co — 全球最大的電子音樂與 DJ 文化平台。
擷取方式：嘗試從 /reviews/singles 頁面提取曲目。
注意：RA 為 React 單頁應用，大部分內容由 JavaScript 動態渲染，
靜態 HTML 擷取的結果可能非常有限。未來可考慮整合 Playwright。
"""

import logging

from bs4 import BeautifulSoup

from .base import BaseScraper, Track
from ..config import MAX_TRACKS_PER_SOURCE

logger = logging.getLogger(__name__)

# /tracks 會重新導向至 /reviews/singles
URLS = [
    "https://ra.co/reviews/singles",
    "https://ra.co/tracks",
]


class ResidentAdvisorScraper(BaseScraper):
    name = "Resident Advisor"

    def fetch_tracks(self) -> list[Track]:
        tracks: list[Track] = []

        for url in URLS:
            try:
                resp = self._get(url)
            except Exception:
                continue

            soup = BeautifulSoup(resp.text, "lxml")

            # RA 為 React 應用，嘗試從伺服器端渲染的 HTML 中提取
            for item in soup.select(
                "li a, article a, [class*='track'] a, [class*='Track'] a, h3 a"
            )[:MAX_TRACKS_PER_SOURCE]:
                text = self.clean_text(item.get_text())
                if not text or len(text) < 5:
                    continue

                parsed = self.parse_artist_title(text)
                if parsed:
                    artist, title = parsed
                    tracks.append(Track(artist=artist, title=title, source=self.name))

            if tracks:
                break

        # 去重（同一連結可能被多個選擇器匹配）
        seen = set()
        unique = []
        for t in tracks:
            key = (t.artist.lower(), t.title.lower())
            if key not in seen:
                seen.add(key)
                unique.append(t)

        logger.info(f"Resident Advisor：找到 {len(unique)} 首曲目")
        return unique
