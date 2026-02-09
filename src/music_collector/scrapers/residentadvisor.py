"""Resident Advisor 擷取器（HTML）。

來源：ra.co — 全球最大的電子音樂與 DJ 文化平台。
擷取方式：嘗試從 /reviews/singles 頁面提取曲目。
注意：RA 為 React 單頁應用，靜態 HTML 擷取受限。
啟用 Playwright 時會自動 fallback 至瀏覽器渲染。
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

            # 偵測 JS 渲染：RA 為 Next.js 應用，靜態 HTML 幾乎無內容
            body_text = soup.get_text(strip=True)
            if len(body_text) < 500:
                # 嘗試 Playwright fallback
                html = self._get_rendered(
                    url,
                    wait_selector="[class*='track'], [class*='Track'], article, li a",
                )
                if html:
                    soup = BeautifulSoup(html, "lxml")
                    logger.info("Resident Advisor：透過 Playwright 成功取得渲染頁面")
                else:
                    logger.warning(
                        "Resident Advisor：網站為 Next.js 單頁應用，"
                        "靜態 HTML 無有效內容。設定 ENABLE_PLAYWRIGHT=true 以啟用瀏覽器渲染。"
                    )
                    return tracks

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
