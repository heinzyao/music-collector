"""Consequence of Sound 擷取器（HTML）。

來源：consequence.net — 美國綜合音樂媒體，涵蓋搖滾、金屬、嘻哈等類型。
擷取方式：解析「Top Song of the Week」分類頁面的文章標題。
標題格式：
  - 「Heavy Song of the Week: Artist's 'Song Title' Description」
  - 「Song of the Week: Artist – Song Title」
  - 「Staff Picks: Best Songs of the Week ...」（略過）
"""

import logging
import re

from bs4 import BeautifulSoup

from .base import BaseScraper, Track
from ..config import MAX_TRACKS_PER_SOURCE

logger = logging.getLogger(__name__)

# WordPress 分類頁面
URL = "https://consequence.net/category/cos-exclusive-features/top-song-of-the-week/"


class ConsequenceScraper(BaseScraper):
    name = "Consequence"

    def fetch_tracks(self) -> list[Track]:
        tracks: list[Track] = []
        resp = self._get(URL)
        soup = BeautifulSoup(resp.text, "lxml")

        # WordPress 分類彙整頁：標題在 h2>a 或 h3>a 中
        # 只擷取主要內容區的文章標題，避免側邊欄和影片區塊
        for heading in soup.select("h2 a, h3 a")[:MAX_TRACKS_PER_SOURCE]:
            text = self.clean_text(heading.get_text())

            # 只處理包含 "Song of the Week" 的標題
            if "song of the week" not in text.lower():
                continue

            parsed = self._parse_consequence_title(text)
            if parsed:
                artist, title = parsed
                tracks.append(Track(artist=artist, title=title, source=self.name))

        logger.info(f"Consequence：找到 {len(tracks)} 首曲目")
        return tracks

    @staticmethod
    def _parse_consequence_title(text: str) -> tuple[str, str] | None:
        """解析 Consequence 文章標題，提取藝人與曲名。

        Consequence 標題格式較為複雜，常見模式：
          - "Poison Ruin Go Medieval Motörhead on \"Eidolon\""
          - "Exodus' \"3111\" Marks Triumphant Return..."
          - "Black Veil Brides Continue Artistic Leap with Alt-Metal Banger \"Certainty\""
          - "The Casualties' Punk-Rock Protest Anthem \"People Over Power\""

        策略：提取引號中的曲名後，將前綴中的動詞片語去除，只保留藝人名。
        """
        # 略過彙整文章（非單曲推薦）
        lower = text.lower()
        if any(
            kw in lower
            for kw in [
                "staff picks",
                "best songs of the week",
                "songs of the week",
                "best albums",
                "best music",
                "new album",
                "tour",
                "interview",
                "evolution",
                "crate digging",
            ]
        ):
            return None

        # 移除前綴（如 "Heavy Song of the Week:"）
        colon_idx = text.find(":")
        if colon_idx != -1:
            text = text[colon_idx + 1 :].strip()

        # 嘗試從引號中提取曲名
        # 注意：不能將直引號 ' 放入字元集，否則所有格的 ' 會被誤判為開引號
        # 支援：" "（直雙引號）、\u201c \u201d（彎雙引號）、\u2018 \u2019（彎單引號）
        m = re.search(
            r'["\u201c\u201d\u2018\u2019]+(.+?)["\u201c\u201d\u2018\u2019]+', text
        )
        if m:
            title = m.group(1).strip()
            prefix = text[: m.start()].strip()

            # 從 prefix 中去除動詞片語，只保留藝人名
            artist = BaseScraper._extract_artist_before_verb(prefix, _VERB_PATTERNS)

            # 移除藝人名末尾的所有格 's 或 '
            artist = re.sub(r"['\u2019]s?\s*$", "", artist).strip()

            if artist and title:
                return artist, title

        # 備選：「Artist – Title」格式
        for sep in [" – ", " - ", " — "]:
            if sep in text:
                parts = text.split(sep, 1)
                return parts[0].strip(), parts[1].strip()

        return None


# 常見動詞模式：用於辨識藝人名結束、描述文字開始的位置
_VERB_PATTERNS = re.compile(
    r"\b(?:"
    # 常見的動作動詞（第三人稱、複數、原形）
    r"Go(?:es)?|Bring(?:s)?|Take(?:s)?|Make(?:s)?|Lock(?:s)?|Mark(?:s)?|"
    r"Drop(?:s)?|Return(?:s)?|Release(?:s)?|Deliver(?:s)?|Share(?:s)?|"
    r"Unveil(?:s)?|Debut(?:s)?|Announce(?:s)?|Explore(?:s)?|Channel(?:s)?|"
    r"Capture(?:s)?|Embrace(?:s)?|Find(?:s)?|Reveal(?:s)?|Offer(?:s)?|"
    r"Open(?:s)?|Close(?:s)?|Play(?:s)?|Feel(?:s)?|Move(?:s)?|Give(?:s)?|"
    r"Continue(?:s)?|Celebrate(?:s)?|Launch(?:es)?|Showcase(?:s)?|"
    r"Premiere(?:s)?|Introduce(?:s)?|Present(?:s)?|Tackle(?:s)?|"
    r"Unleash(?:es)?|Confront(?:s)?|Navigate(?:s)?|Demand(?:s)?|"
    r"Paint(?:s)?|Steer(?:s)?|Wade(?:s)?|Resurrect(?:s)?|Sharpen(?:s)?|"
    r"Soar(?:s)?|Dive(?:s)?|Wrestle(?:s)?|Wage(?:s)?|Salute(?:s)?|"
    r"Tap(?:s)?|Hit(?:s)?|Get(?:s)?|Put(?:s)?|Set(?:s)?|Cut(?:s)?|"
    r"Team(?:s)?|Join(?:s)?|Lead(?:s)?|Ride(?:s)?|Rise(?:s)?|Talk(?:s)?|"
    # 動詞描述短語的起始字
    r"Is|Are|Has|Have|Had|Was|Were|Will|Would|Can|Could|"
    # 所有格名詞後常接的描述性名詞短語
    r"Punk-Rock|Alt-Metal|Hard-Hitting|Full-Intensity|"
    r"New|Latest|Signature|Artistic|Triumphant"
    r")\b",
    re.IGNORECASE,
)
