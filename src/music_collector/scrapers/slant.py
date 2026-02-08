"""Slant Magazine 擷取器（HTML）。

來源：slantmagazine.com — 美國影音評論雜誌，以嚴謹的樂評著稱。
擷取方式：解析音樂分類頁面的樂評標題。
標題格式：「Artist 'Album/Track Title' Review: Description」
  例如：「FKA twigs 'Eusexua Afterglow' Review — Basking in the Pleasure Principle」
"""

import logging
import re

from bs4 import BeautifulSoup

from .base import BaseScraper, Track
from ..config import MAX_TRACKS_PER_SOURCE

logger = logging.getLogger(__name__)

# 嘗試多個 URL 模式（Slant 可能對部分路徑啟用反爬蟲）
URLS = [
    "https://www.slantmagazine.com/music/",
    "https://www.slantmagazine.com/category/music/",
]


class SlantScraper(BaseScraper):
    name = "Slant"

    def fetch_tracks(self) -> list[Track]:
        tracks: list[Track] = []

        for url in URLS:
            try:
                resp = self._get(url)
            except Exception:
                continue

            soup = BeautifulSoup(resp.text, "lxml")

            # 偵測 JS 渲染 / Cloudflare 挑戰頁
            body_text = soup.get_text(strip=True).lower()
            if any(
                indicator in body_text
                for indicator in [
                    "enable javascript",
                    "checking your browser",
                    "just a moment",
                    "cloudflare",
                ]
            ):
                logger.warning(
                    "Slant：網站被 Cloudflare JS 挑戰阻擋，無法以靜態 HTML 擷取。"
                    "未來可考慮整合 Playwright。"
                )
                return tracks

            for heading in soup.select(
                "h2 a, h3 a, .post-title a, article h2, .entry-title a"
            )[:MAX_TRACKS_PER_SOURCE]:
                text = self.clean_text(heading.get_text())

                # 略過非音樂內容
                if any(
                    skip in text.lower()
                    for skip in [
                        "best of",
                        "worst of",
                        "ranked",
                        "interview",
                        "the 25",
                        "film",
                        "tv",
                    ]
                ):
                    continue

                parsed = self._parse_slant_title(text)
                if parsed:
                    artist, title = parsed
                    tracks.append(Track(artist=artist, title=title, source=self.name))

            if tracks:
                break

        logger.info(f"Slant：找到 {len(tracks)} 首曲目")
        return tracks

    @staticmethod
    def _parse_slant_title(text: str) -> tuple[str, str] | None:
        """解析 Slant 樂評標題，提取藝人與專輯/曲目名。"""
        # 從引號中提取專輯/曲名
        m = re.search(r"['\u2018\u201c\"]+(.+?)['\u2019\u201d\"]+", text)
        if m:
            title = m.group(1).strip()
            artist = text[: m.start()].strip()
            if artist and title:
                return artist, title

        # 備選：移除 "Review:" 前綴後嘗試「Artist – Title」格式
        if text.lower().startswith("review:"):
            text = text[7:].strip()

        for sep in [" – ", " - ", " — "]:
            if sep in text:
                parts = text.split(sep, 1)
                return parts[0].strip(), parts[1].strip()

        return None
