"""Rolling Stone 擷取器（HTML）。

來源：rollingstone.com — 全球知名音樂與流行文化雜誌。
擷取方式：從音樂清單頁面尋找當年或去年的「best songs」年度清單，
進入清單頁後從標題中提取曲目。
注意：Rolling Stone 的清單通常在年底發布，年初可能無新清單。
"""

import logging
from datetime import datetime

from bs4 import BeautifulSoup

from .base import BaseScraper, Track
from ..config import MAX_TRACKS_PER_SOURCE

logger = logging.getLogger(__name__)

# 音樂清單索引頁
URL = "https://www.rollingstone.com/music/music-lists/"


class RollingStoneScraper(BaseScraper):
    name = "Rolling Stone"

    def fetch_tracks(self) -> list[Track]:
        tracks: list[Track] = []
        resp = self._get(URL)
        soup = BeautifulSoup(resp.text, "lxml")

        current_year = datetime.now().year

        # 搜尋「best songs」清單連結（限當年或去年）
        best_songs_url = None
        for link in soup.select("a[href]")[:200]:
            href = link.get("href", "")
            text = link.get_text().lower()
            if ("best-songs" in href or "best songs" in text) and (
                str(current_year) in href or str(current_year - 1) in href
            ):
                best_songs_url = href
                break

        if not best_songs_url:
            logger.info("Rolling Stone：未找到當期 best-songs 清單")
            return tracks

        # 補全相對路徑
        if best_songs_url.startswith("/"):
            best_songs_url = "https://www.rollingstone.com" + best_songs_url

        try:
            resp = self._get(best_songs_url)
        except Exception as e:
            logger.warning(f"Rolling Stone：清單頁面擷取失敗：{e}")
            return tracks

        soup = BeautifulSoup(resp.text, "lxml")

        # 從清單項目標題中提取曲目
        for heading in soup.select("h2, h3, .c-gallery-vertical-album__title"):
            text = self.clean_text(heading.get_text())
            parsed = self.parse_artist_title(text)
            if parsed:
                artist, title = parsed
                tracks.append(Track(artist=artist, title=title, source=self.name))

        logger.info(f"Rolling Stone：找到 {len(tracks[:MAX_TRACKS_PER_SOURCE])} 首曲目")
        return tracks[:MAX_TRACKS_PER_SOURCE]
