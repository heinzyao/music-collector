"""SPIN 擷取器（RSS）。

來源：spinmagazine.com — 美國搖滾與流行音樂雜誌。
擷取方式：解析 /new-music/ 的 RSS feed。

原本解析 HTML 標題並靠動詞清單切出藝人名，但 SPIN 的標題是敘述句，
藝人不一定在句首（「Critics Are Hailing 'The Gold Album' as Weezer's
Return to Form」），動詞清單永遠補不齊。改用 feed 的 category tag 取藝人 —
與 DIY 擷取器同一招，差別是 DIY 要求 tag 出現在標題開頭，SPIN 的藝人常在
句中，所以只要求出現在標題任一處。
"""

import logging
import re
import unicodedata

import feedparser

from .base import BaseScraper, Track
from ..config import MAX_TRACKS_PER_SOURCE

logger = logging.getLogger(__name__)

FEED_URL = "https://www.spinmagazine.com/new-music/feed/"

# 曲名：typographic 引號。negative lookahead 避免縮寫撇號（Where's）被當成結尾引號
QUOTED = re.compile(r"[‘“](.+?)(?:’(?![a-zA-Z])|”)")

# 欄目、分類與系統 tag，不是藝人名
_NON_ARTIST_TAGS = {
    "new music",
    "reviews",
    "news",
    "features",
    "lists",
    "interviews",
    "album review",
    "ep review",
    "single review",
    "uncategorized",
    "pushly",
}

# 非新歌發布的內容，整篇跳過
_SKIP_KEYWORDS = [
    "interview",
    "obituary",
    "dies",
    "dead",
    "death",
    "tour",
    "festival",
    "halftime",
    "super bowl",
    "teases new music",
]


class SpinScraper(BaseScraper):
    name = "SPIN"

    def fetch_tracks(self) -> list[Track]:
        tracks: list[Track] = []
        feed = feedparser.parse(FEED_URL)

        if feed.bozo and not feed.entries:
            logger.warning("SPIN：RSS feed 解析失敗")
            return tracks

        for entry in feed.entries[:MAX_TRACKS_PER_SOURCE]:
            text = self.clean_text(entry.get("title", ""))
            if not text or len(text) < 10:
                continue

            lower = text.lower()
            if any(kw in lower for kw in _SKIP_KEYWORDS):
                continue

            title = self._extract_title(text)
            if not title:
                continue

            categories = [c.get("term", "") for c in entry.get("tags", [])]
            artist = self._match_artist_tag(text, categories)
            if artist:
                tracks.append(Track(artist=artist, title=title, source=self.name))

        unique = self._deduplicate_tracks(tracks)
        logger.info(f"SPIN：找到 {len(unique)} 首曲目")
        return unique

    @staticmethod
    def _extract_title(text: str) -> str | None:
        """取出引號中的曲名。沒有引號代表標題沒帶作品名，無法送去 Spotify 搜尋。

        只清掉逗號句號分號冒號 —— 那是美式排版塞進引號內的句讀（'Mirrors,'）。
        問號驚嘆號會留著，它們通常是曲名的一部分（'WHO ASKED?'）。
        """
        m = QUOTED.search(text)
        if not m:
            return None
        return m.group(1).strip().rstrip(",.;:") or None

    @staticmethod
    def _match_artist_tag(text: str, categories: list[str]) -> str | None:
        """回傳出現在標題中的那個 tag 作為藝人名。

        tag 清單同時含藝人與欄目名，且一篇文章可能帶多個藝人 tag（文中提到的
        其他樂團）—— 只有真正的主角會出現在標題裡。取最長的吻合結果。

        比對時去除重音：SPIN 的 tag 常寫成 ASCII（Beyonce）而標題用重音
        （Beyoncé）。
        """
        folded_text = _fold(text)
        hits = [
            c
            for c in categories
            if c and c.lower() not in _NON_ARTIST_TAGS and _fold(c) in folded_text
        ]
        if not hits:
            return None

        artist = max(hits, key=len)
        # tag 全小寫代表原始大小寫已遺失，補回標題式大小寫（MGMT 這類含大寫的 tag 不動）
        return artist.title() if artist.islower() else artist


def _fold(text: str) -> str:
    """小寫並移除重音，用於比對。"""
    decomposed = unicodedata.normalize("NFKD", text)
    return "".join(c for c in decomposed if not unicodedata.combining(c)).lower()
