"""The Line of Best Fit 擷取器（HTML）。

來源：thelineofbestfit.com — 英國獨立音樂評論網站，以「Song of the Day」聞名。
擷取方式：解析 /tracks 頁面中的文章連結。
標題格式：「ARTIST NAME [動詞描述] 'Song Title'」
  例如：「MX LONELY numb the pain on full-intensity eruption 'Anesthetic'」

藝人名以文章 URL slug 定位（/tracks/yuma-koda-ende → 藝人 slug 在最前面），
比從敘述句猜動詞邊界可靠。LOBF 的 RSS 只有 News、不含 track 評論，也沒有
藝人 tag，所以無法比照 SPIN 用 category。
"""

import logging
import re

from bs4 import BeautifulSoup

from .base import BaseScraper, Track, slugify
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

            parsed = self._parse_lobf_title(text, link.get("href", ""))
            if parsed:
                artist, title = parsed
                tracks.append(Track(artist=artist, title=title, source=self.name))

        unique = self._deduplicate_tracks(tracks)
        logger.info(f"Line of Best Fit：找到 {len(unique)} 首曲目")
        return unique

    @staticmethod
    def _parse_lobf_title(text: str, href: str = "") -> tuple[str, str] | None:
        """解析 LOBF 文章標題，提取藝人與曲名。

        LOBF 標題格式：「ARTIST NAME [動詞描述] 'Song Title'」
        策略：先從末尾引號中提取曲名，再用 URL slug 定位藝人名；
        slug 對不上時退回大小寫與所有格的啟發式規則。
        """
        found = _last_quoted(text)
        if not found:
            return None
        title, quote_start = found

        prefix = text[:quote_start].strip()

        # === 策略 0：URL slug（最可靠）===
        artist = _artist_from_slug(prefix, href)
        if artist:
            return artist, title

        # === 策略 1：處理所有格 's ===
        # "Charlie Le Mindu's musical project MUCHAS PROBLEMAS..." → "Charlie Le Mindu"
        possessive_m = re.match(r"^(.+?)['\u2019]s\s+", prefix)
        if possessive_m:
            artist = possessive_m.group(1).strip()
            if artist:
                return artist, title

        # === 策略 2：大寫字開頭，遇到小寫字（動詞）即停止 ===
        # 後續的字可以是另一個大寫字，或清單內的小寫連接詞。
        # 原本少了字與字之間的 \s+，"Phoebe Bridgers" 這種多字藝人名一直匹配不到。
        artist_m = re.match(
            r"^("
            r"[A-Z0-9\u00C0-\u024F][\w.\u00C0-\u024F-]*"
            r"(?:\s+(?:and|&|the|of|de|von|van|feat\.?|ft\.?|x|vs\.?"
            r"|[A-Z0-9\u00C0-\u024F][\w.\u00C0-\u024F-]*))*"
            r")"
            r"(?:\s+[a-z])",
            prefix,
        )
        if artist_m:
            artist = artist_m.group(1).strip()
            if artist:
                return artist, title

        return None


# 曲名在標題末尾的引號中。引號成對匹配並取「最後一組」：
# 「iKeda brings ‘bubble riddim’ universe to life on “Go!”」有兩組引號，
# 混用字元集會從第一個開引號一路吃到最後一個收引號。
_QUOTED = re.compile(
    r"\u2018([^\u2019]+)\u2019"
    r"|\u201c([^\u201d]+)\u201d"
    r"|\"([^\"]+)\""
)


def _last_quoted(text: str) -> tuple[str, int] | None:
    """取標題中最後一組成對引號，回傳（曲名, 起始位置）—— 曲名固定在句末。"""
    matches = list(_QUOTED.finditer(text))
    if not matches:
        return None
    last = matches[-1]
    title = next(g for g in last.groups() if g is not None)
    return title.strip(), last.start()


def _artist_from_slug(prefix: str, href: str) -> str | None:
    """用文章 URL slug 決定 prefix 中哪幾個字是藝人名。

    slug 形如 yuma-koda-ende（藝人在前、曲名在後），所以取「最長且是 slug
    前綴」的那組字。文字仍取自標題以保留原本的大小寫與標點。
    & 在 LOBF 的 slug 中直接消失（captain-tallen-the-benevolent-entities），
    故兩種寫法都試。
    """
    if not href or not prefix:
        return None

    slug = href.rstrip("/").rsplit("/", 1)[-1]
    words = prefix.split()
    for n in range(len(words), 0, -1):
        candidate = " ".join(words[:n])
        for variant in (slugify(candidate), slugify(candidate, amp=" ")):
            if variant and (slug == variant or slug.startswith(variant + "-")):
                # slug 比對時已忽略所有格，回傳的文字也要一併去掉
                return re.sub(r"['\u2019]s?$", "", candidate).strip()
    return None
