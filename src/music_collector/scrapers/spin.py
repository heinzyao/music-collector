"""SPIN 擷取器（HTML）。

來源：spin.com — 美國搖滾與流行音樂雜誌。
擷取方式：解析 /new-music/ 分類頁面的文章標題。
標題格式：以敘述性標題呈現，曲名出現在引號中。
  例如：「Cat Power Takes Us Back In Time With New EP 'Redux'」
  例如：「Blackwater Holylight Explore Darkness on 'Not Here Not Gone'」
"""

import logging
import re

from bs4 import BeautifulSoup

from .base import BaseScraper, Track
from ..config import MAX_TRACKS_PER_SOURCE

logger = logging.getLogger(__name__)

URL = "https://www.spin.com/new-music/"


class SpinScraper(BaseScraper):
    name = "SPIN"

    def fetch_tracks(self) -> list[Track]:
        tracks: list[Track] = []

        try:
            resp = self._get(URL)
        except Exception as e:
            logger.warning(f"SPIN：頁面請求失敗: {e}")
            return tracks

        soup = BeautifulSoup(resp.text, "lxml")

        for heading in soup.select("h3.entry-title")[:MAX_TRACKS_PER_SOURCE]:
            text = self.clean_text(heading.get_text())
            if not text or len(text) < 10:
                continue

            parsed = self._parse_spin_title(text)
            if parsed:
                artist, title = parsed
                tracks.append(Track(artist=artist, title=title, source=self.name))

        # 去重
        seen = set()
        unique = []
        for t in tracks:
            key = (t.artist.lower(), t.title.lower())
            if key not in seen:
                seen.add(key)
                unique.append(t)

        logger.info(f"SPIN：找到 {len(unique)} 首曲目")
        return unique

    @staticmethod
    def _parse_spin_title(text: str) -> tuple[str, str] | None:
        """解析 SPIN 文章標題，提取藝人與曲名。

        SPIN 標題格式為敘述性句子，主要模式：
          1. "Blackwater Holylight Explore Darkness on 'Not Here Not Gone'"
             → Artist [verb...] on 'Title'
          2. "On Kelly Moran's 'Mirrors,' All Is Not What It Seems"
             → On Artist's 'Title' [...]
          3. "30 Years Later, 'The Ghost of Tom Joad' Reminds Us..."
             → [非藝人前綴], 'Title' [...]  — 略過，無法辨識藝人
          4. "Melody's Echo Chamber Ascends Heavenward On 'Unclouded'"
             → Artist [verb...] On 'Title'
          5. "Cat Power Takes Us Back In Time With New EP 'Redux'"
             → Artist [verb...] 'Title'

        策略：使用 typographic 引號定位曲名，再從前綴提取藝人名。
        """
        # 略過非音樂內容
        lower = text.lower()
        if any(
            kw in lower
            for kw in [
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
                "let it be",
            ]
        ):
            return None

        # 從 typographic 引號中提取曲名
        # 使用 negative lookahead (?![a-zA-Z]) 避免將縮寫撇號（如 Where's）誤判為結尾引號
        m = re.search(r"[\u2018\u201c](.+?)(?:\u2019(?![a-zA-Z])|\u201d)", text)
        if not m:
            return None

        title = m.group(1).strip()
        # 移除引號內曲名尾端的標點（逗號、句號、分號等）
        title = title.rstrip(".,;:!?")
        prefix = text[: m.start()].strip()

        if not title:
            return None

        # === 模式：prefix 以 "On" 開頭（介詞引導句） ===
        if prefix.lower().startswith("on "):
            # "On Kelly Moran's 'Mirrors,'" → artist = "Kelly Moran"
            inner = prefix[3:].strip()  # 移除 "On "
            # 移除所有格
            inner = re.sub(r"['\u2019]s?\s*$", "", inner).strip()
            if inner:
                return inner, title
            return None

        # === 略過：prefix 以數字開頭或看起來不像藝人名 ===
        if re.match(r"^\d+\s+", prefix) or not prefix:
            return None

        # 移除所有格 's
        prefix = re.sub(r"['\u2019]s\s*$", "", prefix).strip()

        # 移除 filler 詞如 "With New EP", "On Debut LP"
        prefix = re.sub(
            r"\s+(?:With\s+)?(?:New\s+|Debut\s+)?(?:EP|LP|Album|Single)\s*$",
            "",
            prefix,
            flags=re.IGNORECASE,
        ).strip()

        # 從 prefix 中提取藝人名（去除動詞片語）
        artist = _extract_artist(prefix)

        if artist and title:
            return artist, title

        return None


# 動詞模式：用於辨識藝人名與描述文字的邊界
_VERB_RE = re.compile(
    r"\b(?:"
    r"Takes?|Brings?|Makes?|Finds?|Sees?|Grows?|Drops?|Gets?|Puts?|"
    r"Shares?|Unveils?|Releases?|Delivers?|Debuts?|Announces?|"
    r"Explores?|Channels?|Captures?|Embraces?|Confronts?|"
    r"Navigates?|Returns?|Continues?|Celebrates?|Enlivens?|"
    r"Ascends?|Soars?|Dives?|Rides?|Rises?|Leads?|"
    r"Opens?|Closes?|Plays?|Feels?|Moves?|Gives?|"
    r"Joins?|Teams?|Taps?|Hits?|Cuts?|Runs?|Turns?|"
    r"Keeps?|Holds?|Stands?|Tells?|Calls?|Shows?|"
    r"Wants?|Needs?|Looks?|Creates?|Builds?|Picks?|"
    r"Stays?|Dances?|Reminds?|Proves?|Lets?|"
    r"Is|Are|Has|Have|Had|Was|Were|Will|Would|Still"
    r")\b",
)


def _extract_artist(prefix: str) -> str:
    """從標題前綴中提取藝人名，去除動詞片語。"""
    words = prefix.split()
    if not words:
        return prefix

    for i in range(1, len(words)):
        word = words[i]
        clean_word = re.sub(r"[^\w'-]", "", word)
        if _VERB_RE.fullmatch(clean_word):
            candidate = " ".join(words[:i]).strip()
            if candidate:
                return candidate

    return prefix
