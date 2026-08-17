"""Slant Magazine 擷取器（HTML）。

來源：slantmagazine.com — 美國影音評論雜誌，以嚴謹的樂評著稱。
擷取方式：解析音樂分類頁面的樂評標題。

Slant 有三種標題格式，藝人的位置不同：
  1. 「Artist ‘Title’ Review: Description」            藝人在引號前
     例：Ravyn Lenae ‘Blue Island’ Review: Pop Ambition That Lacks Conviction
  2. 「Review: With ‘Title,’ Artist <動詞片語>」        藝人在引號「之後」
     例：Review: With ‘Hazel Eyes,’ Sam Smith Finds Freedom in Imperfection
  3. 「Review: Artist’s ‘Title’ <動詞片語>」            藝人在引號前但帶所有格
     例：Review: Icona Pop’s ‘Ritual’ Is Preoccupied with Change

格式 2、3 的逗號依美式排版習慣放在引號內，需從曲名尾端移除。
"""

import logging
import re

from bs4 import BeautifulSoup

from .base import BaseScraper, Track
from ..config import MAX_TRACKS_PER_SOURCE

logger = logging.getLogger(__name__)

# 嘗試多個 URL 模式（Slant 可能對部分路徑啟用反爬蟲）
URLS = [
    "https://www.slantmagazine.com/music/",
    "https://www.slantmagazine.com/category/music/",
]


class SlantScraper(BaseScraper):
    name = "Slant"

    def fetch_tracks(self) -> list[Track]:
        tracks: list[Track] = []

        for url in URLS:
            try:
                resp = self._get(url)
            except Exception:
                continue

            soup = BeautifulSoup(resp.text, "lxml")

            # 偵測 JS 渲染 / Cloudflare 挑戰頁
            body_text = soup.get_text(strip=True)
            if self._is_js_blocked(body_text):
                logger.warning(
                    "Slant：網站被 Cloudflare JS 挑戰阻擋，無法以靜態 HTML 擷取。"
                    "未來可考慮整合 Playwright。"
                )
                return tracks

            for heading in soup.select(
                "h2 a, h3 a, .post-title a, article h2, .entry-title a"
            )[:MAX_TRACKS_PER_SOURCE]:
                text = self.clean_text(heading.get_text())

                # 略過非音樂內容
                if self._should_skip(text):
                    continue

                # 只處理樂評標題（含 "Review"），排除新聞類標題
                if "review" not in text.lower():
                    continue

                parsed = self._parse_slant_title(text)
                if parsed:
                    artist, title = parsed
                    tracks.append(Track(artist=artist, title=title, source=self.name))

            if tracks:
                break

        logger.info(f"Slant：找到 {len(tracks)} 首曲目")
        return tracks

    @staticmethod
    def _should_skip(text: str) -> bool:
        """判斷標題是否為非音樂內容。

        跳過詞只比對引號外的文字 —— 曲名本身可能含有 "Film"、"TV"、"Best of"
        （例：Charli XCX ‘Music, Fashion, Film’），比對整串會把樂評一起誤殺。
        """
        outside = _QUOTED_RE.sub(" ", text).lower()
        return any(skip in outside for skip in _SKIP_WORDS)

    @staticmethod
    def _parse_slant_title(text: str) -> tuple[str, str] | None:
        """解析 Slant 樂評標題，提取藝人與專輯/曲目名。"""
        # 從引號中提取專輯/曲名
        m = _QUOTED_RE.search(text)
        if m:
            # 逗號、分號依美式排版放在引號內，不屬於曲名
            title = m.group(1).strip().rstrip(",;:")
            prefix = _REVIEW_PREFIX_RE.sub("", text[: m.start()]).strip()

            if prefix.lower() in _LEAD_IN_WORDS:
                # 格式 2：引號前只剩介系詞 → 藝人在引號之後，切到第一個動詞
                suffix = text[m.end() :].strip()
                artist = BaseScraper._extract_artist_before_verb(suffix, _VERB_RE)
                # 找不到動詞時 helper 會原樣回傳整句。此時寧可放棄也不要寫入垃圾，
                # 因為 DB 的 UNIQUE(artist, title) 會讓爛資料永久留存。
                if artist == suffix:
                    return None
            else:
                # 格式 1／3：藝人在引號前，去掉可能的所有格
                artist = _POSSESSIVE_RE.sub("", prefix).strip()

            if artist and title:
                return artist, title

        # 備選：移除 "Review:" 前綴後嘗試「Artist – Title」格式
        text = _REVIEW_PREFIX_RE.sub("", text).strip()

        for sep in [" – ", " - ", " — "]:
            if sep in text:
                parts = text.split(sep, 1)
                return parts[0].strip(), parts[1].strip()

        return None


_QUOTED_RE = re.compile(r"['‘“\"]+(.+?)['’”\"]+")
_REVIEW_PREFIX_RE = re.compile(r"^review:\s*", re.IGNORECASE)

# 非音樂內容的關鍵字（只比對引號外）
_SKIP_WORDS = ("best of", "worst of", "ranked", "interview", "the 25", "film", "tv")
_POSSESSIVE_RE = re.compile(r"[’']s$")

# 引號前若只剩這些字，代表藝人排在引號之後（格式 2）
_LEAD_IN_WORDS = {"with", "on", "in", "for", "at", "after", ""}

# 動詞模式：辨識藝人名結束、描述文字開始的位置。
# ponytail: 這是本 repo 第 5 份動詞清單（nme/spin/consequence/lineofbestfit 各有一份），
# 各自獨立維護。若開始出現同一個動詞要在多處補的情況，就搬進 base.py 共用。
_VERB_RE = re.compile(
    r"\b(?:"
    r"shares?|unveils?|releases?|announces?|debuts?|delivers?|drops?|"
    r"returns?|confronts?|explores?|channels?|captures?|embraces?|"
    r"finds?|reveals?|offers?|serves?|swings?|falls?|struggles?|"
    r"brings?|opens?|closes?|paints?|wrestles?|navigates?|"
    r"plays?|feels?|demands?|draws?|moves?|gives?|longs?|"
    r"does|do|is|are|was|were|has|have|gets?|"
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
