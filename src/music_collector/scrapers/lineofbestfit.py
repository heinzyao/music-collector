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

        unique = self._deduplicate_tracks(tracks)
        logger.info(f"Line of Best Fit：找到 {len(unique)} 首曲目")
        return unique

    @staticmethod
    def _parse_lobf_title(text: str) -> tuple[str, str] | None:
        """解析 LOBF 文章標題，提取藝人與曲名。

        LOBF 標題格式：「ARTIST NAME [動詞描述] 'Song Title'」
        策略：先從末尾引號中提取曲名，再從開頭提取藝人名。

        藝人名辨識：
          1. 處理所有格（'s）：如 "Charlie Le Mindu's musical project..." → "Charlie Le Mindu"
          2. 正規表達式匹配：藝人名為大寫/首字大寫，第一個全小寫動詞之前的部分
          3. 動詞清單匹配：用擴充的動詞清單作為備選
        """
        # 從末尾的引號中提取曲名
        m = re.search(
            r"['\u2018\u2019\u201c\u201d\"]+(.+?)['\u2018\u2019\u201c\u201d\"]+\s*$",
            text,
        )
        if not m:
            return None
        title = m.group(1).strip()

        prefix = text[: m.start()].strip()

        # === 策略 1：處理所有格 's ===
        # "Charlie Le Mindu's musical project MUCHAS PROBLEMAS..." → "Charlie Le Mindu"
        possessive_m = re.match(r"^(.+?)['\u2019]s\s+", prefix)
        if possessive_m:
            artist = possessive_m.group(1).strip()
            if artist:
                return artist, title

        # === 策略 2：正規表達式 — 大寫字開頭，遇到小寫字（動詞）即停止 ===
        # 允許的小寫連接詞：and, &, the, of, de, von, van, feat, ft, x, vs
        artist_m = re.match(
            r"^("
            r"(?:[A-Z0-9\u00C0-\u024F][\w.\u00C0-\u024F-]*"
            r"(?:\s+(?:and|&|the|of|de|von|van|feat\.?|ft\.?|x|vs\.?)\s+)?)"
            r"+)"
            r"(?:\s+[a-z])",
            prefix,
        )
        if artist_m:
            artist = artist_m.group(1).strip()
            if artist:
                return artist, title

        # === 策略 3：動詞 regex 切分 ===
        artist = BaseScraper._extract_artist_before_verb(prefix, _VERB_RE)
        artist = artist.strip().strip(",").strip()
        if artist and title:
            return artist, title

        return None


# 動詞模式：用於辨識藝人名結束、描述文字開始的位置
_VERB_RE = re.compile(
    r"\b(?:"
    r"shares?|unveils?|releases?|announces?|debuts?|delivers?|drops?|"
    r"returns?|confronts?|explores?|channels?|captures?|embraces?|"
    r"numbs?|skewers?|soars?|dives?|finds?|reveals?|offers?|"
    r"brings?|opens?|closes?|paints?|wrestles?|navigates?|"
    r"plays?|feels?|demands?|draws?|moves?|gives?|longs?|"
    r"marries|marry|steers?|wades?|resurrects?|sharpens?|"
    r"does|do|is|are|has|have|gets?|freezes?|"
    r"takes?|makes?|goes|go|comes?|puts?|sets?|"
    r"rides?|rises?|leads?|hits?|cuts?|runs?|turns?|"
    r"keeps?|holds?|stands?|tells?|calls?|shows?|"
    r"wants?|needs?|looks?|creates?|builds?|picks?|"
    r"teams?|joins?|taps?|imagines?|weaves?|traces?|"
    r"balances?|blends?|crafts?|evokes?|reflects?|"
    r"searches|search|pours?|digs?|strips?|transforms?|breaks?"
    r")\b",
    re.IGNORECASE,
)
