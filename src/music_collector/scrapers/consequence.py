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

from .base import BaseScraper, Track, slugify
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

            parsed = self._parse_consequence_title(text, heading.get("href", ""))
            if parsed:
                artist, title = parsed
                tracks.append(Track(artist=artist, title=title, source=self.name))

        logger.info(f"Consequence：找到 {len(tracks)} 首曲目")
        return tracks

    @staticmethod
    def _parse_consequence_title(text: str, href: str = "") -> tuple[str, str] | None:
        """解析 Consequence 文章標題，提取藝人與曲名。

        Consequence 標題格式較為複雜，常見模式：
          - "Poison Ruin Go Medieval Motörhead on \"Eidolon\""
          - "Exodus' \"3111\" Marks Triumphant Return..."
          - "Black Veil Brides Continue Artistic Leap with Alt-Metal Banger \"Certainty\""
          - "The Casualties' Punk-Rock Protest Anthem \"People Over Power\""

        策略：提取引號中的曲名後，用文章 URL slug 定位藝人名邊界；
        slug 不可用時才退回動詞片語清單。
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

            # 優先用文章 URL slug 定位藝人名邊界。slug 格式為
            # 「(heavy-)song-of-the-week-{artist}-{title}」，比動詞清單可靠：
            # 敘述式標題的動詞（Show/Starts/Transform...）永遠列不完。
            artist = _artist_from_slug(prefix, title, href)

            # 備選：從 prefix 中去除動詞片語，只保留藝人名
            if not artist:
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


def _artist_from_slug(prefix: str, title: str, href: str) -> str:
    """用文章 URL slug 決定 prefix 中哪幾個字是藝人名。

    slug 提供藝人名的「長度」，實際文字仍取自標題，以保留原本的大小寫與標點
    （slug 的 ac-dc 還原不回 AC/DC）。比對不到時回傳空字串交給動詞備選路徑。
    """
    if not href or not prefix:
        return ""

    post = re.sub(r"^.*?song-of-the-week-", "", href.rstrip("/").rsplit("/", 1)[-1])
    if post == href.rstrip("/").rsplit("/", 1)[-1]:
        return ""  # slug 不含預期前綴，格式不符

    artist_slug = re.sub(r"-?" + re.escape(slugify(title)) + r"$", "", post)
    if not artist_slug:
        return ""

    words = prefix.split()
    for n in range(len(words), 0, -1):
        candidate = " ".join(words[:n])
        if slugify(candidate) == artist_slug:
            return re.sub(r"['\u2019]s?$", "", candidate).strip()
    return ""


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
    r"Shred(?:s)?|Doom(?:s)?|Crush(?:es)?|Blast(?:s)?|Rage(?:s)?|Burn(?:s)?|"
    # 動詞描述短語的起始字
    r"Is|Are|Has|Have|Had|Was|Were|Will|Would|Can|Could|"
    # 所有格名詞後常接的描述性名詞短語
    r"Punk-Rock|Alt-Metal|Hard-Hitting|Full-Intensity|"
    r"New|Latest|Signature|Artistic|Triumphant"
    r")\b",
    re.IGNORECASE,
)
