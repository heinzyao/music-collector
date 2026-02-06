"""The Line of Best Fit 擷取器（HTML）。

來源：thelineofbestfit.com — 英國獨立音樂評論網站，以「Song of the Day」聞名。
擷取方式：解析 /tracks 頁面中的文章連結。
標題格式：「ARTIST NAME [動詞描述] 'Song Title'」
  例如：「MX LONELY numb the pain on full-intensity eruption 'Anesthetic'」
  藝人名通常為大寫，曲名在末尾的引號中。
"""

import logging
import re

from bs4 import BeautifulSoup

from .base import BaseScraper, Track
from ..config import MAX_TRACKS_PER_SOURCE

logger = logging.getLogger(__name__)

# /new-music/song-of-the-day 會重新導向至 /tracks
URL = "https://www.thelineofbestfit.com/tracks"


class LineOfBestFitScraper(BaseScraper):
    name = "The Line of Best Fit"

    def fetch_tracks(self) -> list[Track]:
        tracks: list[Track] = []
        resp = self._get(URL)
        soup = BeautifulSoup(resp.text, "lxml")

        # 擷取所有指向 /tracks/ 的文章連結
        for link in soup.select("a[href*='/tracks/']")[:MAX_TRACKS_PER_SOURCE]:
            text = self.clean_text(link.get_text())
            if not text or len(text) < 10:
                continue

            parsed = self._parse_lobf_title(text)
            if parsed:
                artist, title = parsed
                tracks.append(Track(artist=artist, title=title, source=self.name))

        # 以 (artist, title) 去重（同一頁面可能有重複連結）
        seen = set()
        unique_tracks = []
        for t in tracks:
            key = (t.artist.lower(), t.title.lower())
            if key not in seen:
                seen.add(key)
                unique_tracks.append(t)

        logger.info(f"Line of Best Fit：找到 {len(unique_tracks)} 首曲目")
        return unique_tracks

    @staticmethod
    def _parse_lobf_title(text: str) -> tuple[str, str] | None:
        """解析 LOBF 文章標題，提取藝人與曲名。

        策略：先從末尾引號中提取曲名，再從開頭提取藝人名。
        藝人名通常為全大寫或首字大寫，第一個小寫動詞出現前的部分即為藝人。
        """
        # 從末尾的引號中提取曲名
        m = re.search(r"['\u2018\u2019\u201c\u201d\"]+(.+?)['\u2018\u2019\u201c\u201d\"]+\s*$", text)
        if not m:
            return None
        title = m.group(1).strip()

        # 提取藝人名：用正規表達式找到第一個小寫動詞的位置
        # 藝人名為大寫/首字大寫，第一個小寫字即為動詞開始
        prefix = text[:m.start()].strip()
        artist_m = re.match(
            r"^((?:[A-Z0-9][\w.]*(?:\s+(?:and|&|the|of|de|von|van|feat\.?|ft\.?)\s+)?)+)"
            r"(?:\s+[a-z])",
            prefix,
        )
        if artist_m:
            artist = artist_m.group(1).strip()
        else:
            # 備選策略：用已知動詞清單切分
            verbs = [
                " shares ", " share ", " unveils ", " unveil ", " releases ", " release ",
                " announces ", " announce ", " debuts ", " debut ", " delivers ", " deliver ",
                " drops ", " drop ", " returns ", " return ", " confronts ", " confront ",
                " explores ", " explore ", " channels ", " channel ", " captures ", " capture ",
                " embraces ", " embrace ", " numb ", " numbs ", " skewer ", " skewers ",
                " soars ", " soar ", " dives ", " dive ", " finds ", " find ",
                " reveals ", " reveal ", " offers ", " offer ", " brings ", " bring ",
                " opens ", " open ", " closes ", " close ", " paints ", " paint ",
                " wrestles ", " wrestle ", " navigates ", " navigate ", " plays ", " play ",
                " feels ", " feel ", " demands ", " demand ", " draws ", " draw ",
                " moves ", " move ", " gives ", " give ", " longs ", " long ",
                " marries ", " marry ", " steers ", " steer ", " wades ", " wade ",
                " resurrects ", " resurrect ", " sharpens ", " sharpen ",
                " does ", " do ", " is ", " are ", " has ", " have ", " gets ", " get ",
            ]
            artist = prefix
            for verb in verbs:
                idx = prefix.lower().find(verb)
                if idx != -1:
                    artist = prefix[:idx].strip()
                    break

        artist = artist.strip().strip(",").strip()
        if artist and title:
            return artist, title

        return None
