"""Complex 擷取器（HTML）。

來源：complex.com — 美國嘻哈、R&B、流行文化媒體。
擷取方式：嘗試多個 URL（/music、/tag/best-new-music、/pigeons-and-planes），
從文章標題中提取曲目資訊。
注意：Complex 為 JS 重度渲染網站，啟用 Playwright 時會自動 fallback。
"""

import logging
import re

from bs4 import BeautifulSoup

from .base import BaseScraper, Track
from ..config import MAX_TRACKS_PER_SOURCE

logger = logging.getLogger(__name__)

# 嘗試多個 URL 模式
URLS = [
    "https://www.complex.com/music",
    "https://www.complex.com/tag/best-new-music",
    "https://www.complex.com/pigeons-and-planes",
]


class ComplexScraper(BaseScraper):
    name = "Complex"

    def fetch_tracks(self) -> list[Track]:
        tracks: list[Track] = []

        for url in URLS:
            try:
                resp = self._get(url)
            except Exception:
                continue

            soup = BeautifulSoup(resp.text, "lxml")

            # 偵測 JS 渲染：如果頁面內容極少或含有 JS 挑戰標記
            body_text = soup.get_text(strip=True)
            if len(body_text) < 200 or any(
                indicator in body_text.lower()
                for indicator in [
                    "enable javascript",
                    "checking your browser",
                    "just a moment",
                    "cloudflare",
                ]
            ):
                # 嘗試 Playwright fallback
                html = self._get_rendered(url, wait_selector="article, .music, h2")
                if html:
                    soup = BeautifulSoup(html, "lxml")
                    logger.info("Complex：透過 Playwright 成功取得渲染頁面")
                else:
                    logger.warning(
                        "Complex：網站為 JS 重度渲染，無法以靜態 HTML 擷取。"
                        "設定 ENABLE_PLAYWRIGHT=true 以啟用瀏覽器渲染。"
                    )
                    return tracks

            for heading in soup.select("h2 a, h3 a, article a, .post-title a")[
                :MAX_TRACKS_PER_SOURCE
            ]:
                text = self.clean_text(heading.get_text())
                if not text or len(text) < 5:
                    continue

                # 移除常見前綴
                for prefix in [
                    "Best New Music This Week:",
                    "Best New Music:",
                    "New Music:",
                    "Premiere:",
                    "Stream:",
                    "Listen:",
                ]:
                    if text.lower().startswith(prefix.lower()):
                        text = text[len(prefix) :].strip()

                # 嘗試從引號中提取曲名
                m = re.search(r"['\u2018\u201c\"]+(.+?)['\u2019\u201d\"]+", text)
                if m:
                    title = m.group(1).strip()
                    artist = text[: m.start()].strip().rstrip("'s").rstrip(",").strip()
                    if artist and title:
                        tracks.append(
                            Track(artist=artist, title=title, source=self.name)
                        )
                        continue

                # 備選：標準「Artist – Title」格式
                parsed = self.parse_artist_title(text)
                if parsed:
                    artist, title = parsed
                    tracks.append(Track(artist=artist, title=title, source=self.name))

            if tracks:
                break

        logger.info(f"Complex：找到 {len(tracks)} 首曲目")
        return tracks
