"""SoulBounce 擷取器（RSS）。

來源：soulbounce.com — R&B／neo soul 新歌與樂評。
擷取方式：解析 RSS feed。
標題格式：「Artist verb … ‘Track’」，藝人名放在 category tag。

tag 的寫法常和標題不同：小寫（kevon edmonds）、去重音（mya ↔ Mýa、eric benet）、
直撇號（Sy'rai ↔ Sy’Rai）—— 比對前兩邊都先摺疊成同一形式。
"""

import logging
import re
import unicodedata

import feedparser

from .base import BaseScraper, Track
from ..config import MAX_TRACKS_PER_SOURCE

logger = logging.getLogger(__name__)

FEED_URL = "https://www.soulbounce.com/feed/"

# 引號內的曲名。結尾 ’ 後面接字母時是縮寫撇號（Can’t），不是結尾引號
QUOTED = re.compile(r"[‘“]((?:[^’”]|’(?=[a-zA-Z]))+)[’”]")

ALBUM_WORDS = re.compile(r"\b(album|lp|ep|mixtape|tour|cruise)\b", re.I)
SINGLE_WORDS = re.compile(r"\b(single|track|song|drops?)\b", re.I)

# Events = 巡演／活動；Reviews = 專輯樂評；Relax in Paradise = 訃聞
SKIP_TAGS = {"events", "reviews", "relax in paradise"}


def _fold(text: str) -> str:
    """逐字摺疊大小寫、重音與撇號，且保持長度不變（方便回頭切原字串）。"""
    out = []
    for ch in text:
        if ch in "’‘":
            out.append("'")
            continue
        base = unicodedata.normalize("NFKD", ch)[0]
        out.append(base.lower())
    return "".join(out)


class SoulBounceScraper(BaseScraper):
    name = "SoulBounce"

    def fetch_tracks(self) -> list[Track]:
        tracks: list[Track] = []
        feed = feedparser.parse(FEED_URL)

        if feed.bozo and not feed.entries:
            logger.warning("SoulBounce RSS feed 解析失敗")
            return tracks

        for entry in feed.entries[:MAX_TRACKS_PER_SOURCE]:
            title_text = self.clean_text(entry.get("title", ""))
            categories = [c.get("term", "") for c in entry.get("tags", [])]

            if any(c.lower() in SKIP_TAGS for c in categories):
                continue

            title = self._extract_song_title(title_text)
            if not title:
                continue

            artist = self._match_artist_tag(title_text, categories)
            if artist:
                tracks.append(Track(artist=artist, title=title, source=self.name))

        logger.info(f"SoulBounce：找到 {len(tracks)} 首曲目")
        return tracks

    @staticmethod
    def _extract_song_title(text: str) -> str | None:
        """取引號中的曲名，略過專輯／巡演名（同 DIY 的雙引號規則）。"""
        best = None
        prev_end = 0
        for m in QUOTED.finditer(text):
            # 只看上一組引號之後的字，否則「Album ‘X’ With Lead Single ‘Y’」的 Y
            # 會被前面的 Album 誤判成專輯
            before = text[max(prev_end, m.start() - 30): m.start()]
            prev_end = m.end()
            if ALBUM_WORDS.search(before):
                continue
            if SINGLE_WORDS.search(before):
                return m.group(1).strip()
            best = best or m.group(1).strip()
        return best

    @staticmethod
    def _match_artist_tag(text: str, categories: list[str]) -> str | None:
        """回傳標題開頭吻合的最長 tag；藝人名取標題原文（保留大小寫與重音）。"""
        # 先統一成 NFC：組合字元（e + U+0301）在 _fold 逐字處理下會殘留重音
        text = unicodedata.normalize("NFC", text)
        categories = [unicodedata.normalize("NFC", c) for c in categories]
        folded = _fold(text)
        # 吻合處後面不可緊接字母數字，否則 tag「Car」會吻合「Carly …」
        hits = [
            c for c in categories
            if c and folded.startswith(_fold(c)) and not folded[len(c):len(c) + 1].isalnum()
        ]
        if not hits:
            return None
        return text[: len(max(hits, key=len))].strip()
