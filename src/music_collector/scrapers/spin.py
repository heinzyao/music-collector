"""SPIN 擷取器（HTML）。

來源：spin.com — 美國搖滾與流行音樂雜誌。
擷取方式：解析月度「Now Hear This」精選文章中的曲目清單。
URL 格式依月份動態產生：/YYYY/MM/now-hear-this-mmm-yyyy/
會嘗試當月與上月的文章。
"""

import logging
from datetime import datetime

from bs4 import BeautifulSoup

from .base import BaseScraper, Track
from ..config import MAX_TRACKS_PER_SOURCE

logger = logging.getLogger(__name__)


class SpinScraper(BaseScraper):
    name = "SPIN"

    def fetch_tracks(self) -> list[Track]:
        tracks: list[Track] = []
        now = datetime.now()

        # 依序嘗試當月與上月的「Now Hear This」精選
        for month_offset in [0, 1]:
            month = now.month - month_offset
            year = now.year
            if month < 1:
                month += 12
                year -= 1

            # URL 中的月份為英文縮寫小寫（如 jan、feb）
            month_str = datetime(year, month, 1).strftime("%b").lower()
            url = f"https://www.spin.com/{year}/{month:02d}/now-hear-this-{month_str}-{year}/"

            try:
                resp = self._get(url)
            except Exception:
                continue

            soup = BeautifulSoup(resp.text, "lxml")

            # 從文章內的 h2/h3 標題提取曲目
            for heading in soup.select("article h2, article h3, .entry-content h2, .entry-content h3"):
                text = self.clean_text(heading.get_text())
                parsed = self.parse_artist_title(text)
                if parsed:
                    artist, title = parsed
                    tracks.append(Track(artist=artist, title=title, source=self.name))

            # 備選：從粗體文字或清單項目提取
            if not tracks:
                for item in soup.select(".entry-content p strong, .entry-content li"):
                    text = self.clean_text(item.get_text())
                    parsed = self.parse_artist_title(text)
                    if parsed:
                        artist, title = parsed
                        tracks.append(Track(artist=artist, title=title, source=self.name))

            if tracks:
                break

        logger.info(f"SPIN：找到 {len(tracks[:MAX_TRACKS_PER_SOURCE])} 首曲目")
        return tracks[:MAX_TRACKS_PER_SOURCE]
