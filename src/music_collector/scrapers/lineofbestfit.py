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

        # 以 (artist, title) 去重（同一頁面可能有重複連結）
        seen = set()
        unique_tracks = []
        for t in tracks:
            key = (t.artist.lower(), t.title.lower())
            if key not in seen:
                seen.add(key)
                unique_tracks.append(t)

        logger.info(f"Line of Best Fit：找到 {len(unique_tracks)} 首曲目")
        return unique_tracks

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

        # === 策略 3：擴充動詞清單切分 ===
        verbs = [
            "shares",
            "share",
            "unveils",
            "unveil",
            "releases",
            "release",
            "announces",
            "announce",
            "debuts",
            "debut",
            "delivers",
            "deliver",
            "drops",
            "drop",
            "returns",
            "return",
            "confronts",
            "confront",
            "explores",
            "explore",
            "channels",
            "channel",
            "captures",
            "capture",
            "embraces",
            "embrace",
            "numbs",
            "numb",
            "skewers",
            "skewer",
            "soars",
            "soar",
            "dives",
            "dive",
            "finds",
            "find",
            "reveals",
            "reveal",
            "offers",
            "offer",
            "brings",
            "bring",
            "opens",
            "open",
            "closes",
            "close",
            "paints",
            "paint",
            "wrestles",
            "wrestle",
            "navigates",
            "navigate",
            "plays",
            "play",
            "feels",
            "feel",
            "demands",
            "demand",
            "draws",
            "draw",
            "moves",
            "move",
            "gives",
            "give",
            "longs",
            "long",
            "marries",
            "marry",
            "steers",
            "steer",
            "wades",
            "wade",
            "resurrects",
            "resurrect",
            "sharpens",
            "sharpen",
            "does",
            "do",
            "is",
            "are",
            "has",
            "have",
            "gets",
            "get",
            "freezes",
            "freeze",
            "takes",
            "take",
            "makes",
            "make",
            "goes",
            "go",
            "comes",
            "come",
            "puts",
            "put",
            "sets",
            "set",
            "rides",
            "ride",
            "rises",
            "rise",
            "leads",
            "lead",
            "hits",
            "hit",
            "cuts",
            "cut",
            "runs",
            "run",
            "turns",
            "turn",
            "keeps",
            "keep",
            "holds",
            "hold",
            "stands",
            "stand",
            "tells",
            "tell",
            "calls",
            "call",
            "shows",
            "show",
            "wants",
            "want",
            "needs",
            "need",
            "looks",
            "look",
            "creates",
            "create",
            "builds",
            "build",
            "picks",
            "pick",
            "teams",
            "team",
            "joins",
            "join",
            "taps",
            "tap",
            "imagines",
            "imagine",
            "weaves",
            "weave",
            "traces",
            "trace",
            "balances",
            "balance",
            "blends",
            "blend",
            "crafts",
            "craft",
            "evokes",
            "evoke",
            "reflects",
            "reflect",
            "searches",
            "search",
            "pours",
            "pour",
            "digs",
            "dig",
            "strips",
            "strip",
            "transforms",
            "transform",
            "breaks",
            "break",
        ]
        prefix_lower = prefix.lower()
        best_idx = len(prefix)
        for verb in verbs:
            # 用字邊界匹配（確保是完整單字）
            pattern = f" {verb} "
            idx = prefix_lower.find(pattern)
            if idx != -1 and idx < best_idx:
                best_idx = idx

        if best_idx < len(prefix):
            artist = prefix[:best_idx].strip()
        else:
            artist = prefix

        artist = artist.strip().strip(",").strip()
        if artist and title:
            return artist, title

        return None
