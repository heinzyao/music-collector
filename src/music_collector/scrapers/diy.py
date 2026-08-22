"""DIY 擷取器（RSS）。

來源：diymag.com — 英國獨立樂新聞與樂評。
擷取方式：解析 RSS feed，過濾 News 分類。
標題格式：「Artist shares new single 'Title'」（藝人在前、曲名在引號內）。

與 NME/SPIN 不同，DIY 的 RSS 把藝人名放進 category tag，因此不需要靠動詞邊界
猜測藝人名在哪裡結束 —— 直接拿「標題開頭吻合的那個 tag」即可，既準確又不會壞。
"""

import logging
import re

import feedparser

from .base import BaseScraper, Track
from ..config import MAX_TRACKS_PER_SOURCE

logger = logging.getLogger(__name__)

FEED_URL = "https://diymag.com/feed"

# 引號內的曲名。不收直單引號 '，否則所有格（Sorry's）會被誤判為開引號
QUOTED = re.compile(r"[‘“\"]([^’”\"]+)[’”\"]")

# 引號前若提到這些字，引號內是專輯／EP 名而非曲名
ALBUM_WORDS = re.compile(r"\b(album|lp|ep|mixtape|record)\b", re.I)
# 引號前若提到這些字，引號內確定是曲名
SINGLE_WORDS = re.compile(r"\b(single|track|song|cut)\b", re.I)

# 非單曲發布的欄目，整篇跳過
SKIP_PREFIXES = ("the neu bulletin",)


class DIYScraper(BaseScraper):
    name = "DIY"

    def fetch_tracks(self) -> list[Track]:
        tracks: list[Track] = []
        feed = feedparser.parse(FEED_URL)

        if feed.bozo and not feed.entries:
            logger.warning("DIY RSS feed 解析失敗")
            return tracks

        for entry in feed.entries[:MAX_TRACKS_PER_SOURCE]:
            title_text = self.clean_text(entry.get("title", ""))
            categories = [c.get("term", "") for c in entry.get("tags", [])]

            # 只收 News（新歌發布）。Features/Interviews 是專訪、Reviews 是專輯樂評
            if not any(c.lower() == "news" for c in categories):
                continue
            if title_text.lower().startswith(SKIP_PREFIXES):
                continue

            title = self._extract_song_title(title_text)
            if not title:
                continue

            artist = self._match_artist_tag(title_text, categories)
            if artist:
                tracks.append(Track(artist=artist, title=title, source=self.name))

        logger.info(f"DIY：找到 {len(tracks)} 首曲目")
        return tracks

    @staticmethod
    def _extract_song_title(text: str) -> str | None:
        """取出引號中的曲名，略過專輯名。

        「Jamie T returns with new album 'Ghosts' and shares single 'Sabotage'」
        這類標題有兩組引號，第一組是專輯 —— 依引號前的用字判斷該取哪一組。
        """
        best = None
        for m in QUOTED.finditer(text):
            before = text[: m.start()]
            if ALBUM_WORDS.search(before[-30:]):
                continue          # 專輯名，跳過
            if SINGLE_WORDS.search(before[-30:]):
                return m.group(1).strip()   # 明確是單曲，直接採用
            best = best or m.group(1).strip()
        return best

    @staticmethod
    def _match_artist_tag(text: str, categories: list[str]) -> str | None:
        """回傳「出現在標題開頭」的那個 tag 作為藝人名。

        tag 清單同時含藝人、欄目（News）與作者名，只有藝人會出現在標題開頭。
        取最長的吻合結果，避免「Sorry」比「Sorry State」先被選中。
        """
        lower = text.lower()
        hits = [c for c in categories if c and lower.startswith(c.lower())]
        return max(hits, key=len) if hits else None
