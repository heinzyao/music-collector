"""NME 擷取器（HTML）。

來源：nme.com — 英國歷史最悠久的音樂週刊之一。
擷取方式：解析 /reviews/track 分類頁面中的個別曲目評論標題。
標題格式：
  - 「Artist Name's 'Track Name' review: description」
  - 「Artist – 'Track' single review」
  - 「Is 'Track Name' a ... for Artist?」（較少見）
"""

import logging
import re

from bs4 import BeautifulSoup

from .base import BaseScraper, Track
from ..config import MAX_TRACKS_PER_SOURCE

logger = logging.getLogger(__name__)

# NME 曲目評論分類頁
URL = "https://www.nme.com/reviews/track"


class NMEScraper(BaseScraper):
    name = "NME"

    def fetch_tracks(self) -> list[Track]:
        tracks: list[Track] = []

        try:
            resp = self._get(URL)
        except Exception as e:
            logger.warning(f"NME：頁面請求失敗: {e}")
            return tracks

        soup = BeautifulSoup(resp.text, "lxml")

        # 從曲目評論列表頁提取標題
        for heading in soup.select(
            ".entry-title a, h3.entry-title a, .td_module_wrap .entry-title a"
        )[:MAX_TRACKS_PER_SOURCE]:
            text = self.clean_text(heading.get_text())
            if not text or len(text) < 5:
                continue

            parsed = self._parse_nme_review_title(text)
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

        logger.info(f"NME：找到 {len(unique)} 首曲目")
        return unique

    @staticmethod
    def _parse_nme_review_title(text: str) -> tuple[str, str] | None:
        """解析 NME 曲目評論標題，提取藝人與曲名。

        NME 標題為敘述性句子，主要模式：
          1. "Harry Styles takes things slow on 'Aperture'"
             → Artist [verb...] on 'Title'
          2. "Is 'Opening Night' a curtain call for Arctic Monkeys?"
             → Is/On 'Title' [...] for/by Artist
          3. "Mitski's new single 'Where's My Phone?'"
             → Artist's [filler] 'Title'
          4. "On 'Bloom Baby Bloom', Wolf Alice are..."
             → On 'Title', Artist [verb...]
          5. "GFRIEND remind us ... on 'Season of Memories'"
             → Artist [verb...] on 'Title'
          6. "TWS' new winter single 'Last Festival' is..."
             → Artist' [filler] 'Title'

        策略：使用 typographic 引號（U+2018/U+2019）定位曲名，
        避免與所有格撇號混淆。
        """
        # 略過非曲目內容
        lower = text.lower()
        if any(
            kw in lower
            for kw in [
                "interview",
                "obituary",
                "surprise",
                "release is",
            ]
        ):
            return None

        # === 使用 typographic 引號匹配曲名 ===
        # 優先匹配 U+2018...U+2019 (curly single quotes)
        # 或 U+201C...U+201D (curly double quotes)
        # 使用 negative lookahead (?![a-zA-Z]) 避免將縮寫的撇號（如 Where's）誤判為結尾引號
        m = re.search(r"[\u2018\u201c](.+?)(?:\u2019(?![a-zA-Z])|\u201d)", text)
        if not m:
            # 備選：「Artist – Title」格式
            return _parse_dash_format(text)

        title = m.group(1).strip()

        prefix = text[: m.start()].strip()
        suffix = text[m.end() :].strip()

        # 移除 title 中的 "review" 後綴（如果引號只包住了曲名部分）
        title = re.sub(
            r"\s*(?:review|single review|track review).*$",
            "",
            title,
            flags=re.IGNORECASE,
        ).strip()

        # === 模式 A：標題以 "Is"/"On" 開頭，曲名在前，藝人在後 ===
        if prefix.lower() in ("is", "on", "with", "from", "for"):
            # "Is 'Opening Night' a curtain call for Arctic Monkeys?"
            # "On 'Bloom Baby Bloom', Wolf Alice are..."
            artist = _extract_artist_from_suffix(suffix)
            if artist and title:
                return artist, title
            return None

        # === 模式 B：prefix 為空（曲名在最前面）===
        if not prefix:
            artist = _extract_artist_from_suffix(suffix)
            if artist and title:
                return artist, title
            return None

        # === 模式 C：prefix 包含藝人名 ===
        # 移除 "Artist –" 格式的尾部
        prefix = re.sub(r"\s*[–—-]\s*$", "", prefix).strip()

        # 移除 "filler" 詞：如 "new single", "new winter single", "new EP"
        prefix = re.sub(
            r"['\u2019]s?\s+(?:new\s+)?(?:winter\s+|debut\s+|latest\s+)?(?:single|EP|album|track|song|record|release)\s*$",
            "",
            prefix,
            flags=re.IGNORECASE,
        ).strip()

        # 移除尾部的所有格 's 或 '
        prefix = re.sub(r"['\u2019]s?\s*$", "", prefix).strip()

        # 從 prefix 中提取藝人名（去除動詞片語）
        artist = _extract_artist(prefix)

        if artist and title:
            return artist, title

        return None


def _parse_dash_format(text: str) -> tuple[str, str] | None:
    """解析「Artist – Title」格式。"""
    for sep in [" – ", " — ", " - "]:
        if sep in text:
            parts = text.split(sep, 1)
            artist = parts[0].strip()
            title = parts[1].strip()
            # 移除 "review" 後綴
            title = re.sub(
                r"\s*(?:review|single review|track review).*$",
                "",
                title,
                flags=re.IGNORECASE,
            ).strip()
            # 移除引號
            title = re.sub(
                r"^[\u2018\u201c'\"]+|[\u2019\u201d'\"]+$", "", title
            ).strip()
            if artist and title:
                return artist, title
    return None


def _extract_artist_from_suffix(suffix: str) -> str | None:
    """從標題後半部分提取藝人名。

    處理以下模式：
      - "a curtain call for Arctic Monkeys? It's a beautiful gift" → "Arctic Monkeys"
      - ", Wolf Alice are bolder and more brilliant than ever" → "Wolf Alice"
      - "by Kendrick Lamar is a masterpiece" → "Kendrick Lamar"
    """
    # 移除開頭的逗號和空白
    suffix = re.sub(r"^[,\s]+", "", suffix).strip()

    # 模式 1：「for Artist」
    for_m = re.search(r"\bfor\s+(.+?)(?:\s*[?!.]|\s*$)", suffix)
    if for_m:
        artist = for_m.group(1).strip()
        # 移除尾部描述：「It's ...」
        artist = re.sub(r"\?\s+.*$", "", artist).strip()
        if artist:
            return artist

    # 模式 2：「by Artist」
    by_m = re.search(r"\bby\s+(.+?)(?:\s*[-–—:?!.]|\s*$)", suffix)
    if by_m:
        return by_m.group(1).strip()

    # 模式 3：逗號後直接跟藝人名（如 ", Wolf Alice are..."）
    # 提取逗號後的第一組大寫字作為藝人名
    comma_m = re.match(
        r"^([A-Z][\w]*(?:\s+(?:and|&|the|of|The)\s+[A-Z][\w]*|"
        r"\s+[A-Z][\w]*)*)",
        suffix,
    )
    if comma_m:
        artist = comma_m.group(1).strip()
        # 用動詞清單截斷
        artist = _extract_artist(artist)
        if artist:
            return artist

    return None


# 動詞模式
_VERB_RE = re.compile(
    r"\b(?:"
    r"takes?|brings?|makes?|finds?|sees?|drops?|gets?|puts?|"
    r"shares?|unveils?|releases?|delivers?|debuts?|announces?|"
    r"explores?|channels?|captures?|embraces?|confronts?|"
    r"navigates?|returns?|continues?|celebrates?|"
    r"soars?|dives?|rides?|rises?|leads?|"
    r"opens?|closes?|plays?|feels?|moves?|gives?|"
    r"joins?|teams?|taps?|hits?|cuts?|runs?|turns?|"
    r"keeps?|holds?|stands?|tells?|calls?|shows?|"
    r"wants?|needs?|looks?|creates?|builds?|picks?|"
    r"reminds?|proves?|brings?|"
    r"is|are|has|have|had|was|were|will|would|goes|go"
    r")\b",
    re.IGNORECASE,
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
