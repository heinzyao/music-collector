"""年度／月度單曲榜擷取（各來源共用）。

擷取器設 `list_index_urls`（RSS feed 或 HTML 索引頁），這裡從中找出今年的
單曲榜文章（「The 100 Best Songs of 2026」、「Best Albums and Tracks of
October 2026」、「… So Far」），再逐項解析文章的 h2/h3 標題。

各站的單筆標題格式實測（2025 年度榜）：
  Stereogum      Lorde - "Man Of The Year" (Universal)
  Consequence    Tame Impala — “Dracula”
  Pitchfork      gyrofield: “Vegetation Grows Thick”
  Rolling Stone  Miley Cyrus, ‘End of the World’
  The Quietus    British Murder Boys ‘Get In Line’ Downwards（月榜要從 TRACKS 段之後取）
  DIY            20. Westside Cowboy — Shells（無引號，只在有名次編號時收）

只收單曲榜：標題沒提到 songs/tracks/singles 的專輯榜一律不看（使用者 2026-11-05 指示）。
索引頁混著歷年舊榜，只收標題年份是今年的（使用者 2026-11-05 指示，跨年才出的去年年終榜也不收）。
"""

import logging
import re
from collections import Counter
from datetime import date
from urllib.parse import urljoin, urlparse

import feedparser
from bs4 import BeautifulSoup

from .base import Track

logger = logging.getLogger(__name__)

_MAX_LISTS = 5   # 每個索引最多處理幾篇榜單
_MAX_PAGES = 5   # 分頁榜（The Quietus 年終榜分 3 頁）最多跟幾頁

_SONG_WORDS = re.compile(r"\b(songs?|tracks?|singles)\b", re.I)
_LIST_WORDS = re.compile(r"\b(best|top|favou?rites?|of the (year|month))\b", re.I)
_SKIP_WORDS = re.compile(r"\b(of all time|of the week|this week|weekly|decade)\b", re.I)
_YEAR = re.compile(r"\b(20\d\d)\b(?!s)")

_NUMBERED = re.compile(r"^\s*\d{1,3}[.)]\s*")
# 曲名用成對引號。’ 也可能是開引號（The Quietus：Lifeloose ’07XXXXXXXXX’），
# 但後面要緊接非空白，收尾的 ’ 後面不能接字母（Eternity’s、Ain’t 是撇號）
_QUOTED = re.compile(
    r"^(?P<artist>.{1,100}?)\s*[-–—:,]?\s*"
    r"(?:“(?P<curly>[^”]+)”|\"(?P<straight>[^\"]+)\"|[‘’](?=\S)(?P<single>.+?)’(?![A-Za-z]))"
)
_DASHED = re.compile(r"^(?P<artist>.{1,100}?)\s+[–—-]\s+(?P<title>.{1,150})$")


def is_list_title(title: str, today: date | None = None) -> bool:
    """標題是不是今年的單曲榜（使用者 2026-11-05 指示只收今年度）。"""
    today = today or date.today()
    if not (_SONG_WORDS.search(title) and _LIST_WORDS.search(title)):
        return False
    if _SKIP_WORDS.search(title):
        return False
    return str(today.year) in _YEAR.findall(title)


def parse_entry(text: str) -> tuple[str, str] | None:
    """解析一則榜單標題，回傳 (artist, title)。"""
    text = re.sub(r"[​‌‍]", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    numbered = _NUMBERED.match(text)
    text = text[numbered.end():] if numbered else text
    m = _QUOTED.match(text) or (_DASHED.match(text) if numbered else None)
    if not m:
        return None
    artist = m["artist"].strip().rstrip(",:-–— ").strip()
    title = next(g for g in (m.groupdict().get(k) for k in ("curly", "straight", "single", "title")) if g)
    title = title.strip()
    return (artist, title) if artist and title else None


def parse_list_page(html: str, url: str) -> tuple[list[tuple[str, str]], str | None]:
    """解析榜單頁，回傳 (曲目, 下一頁網址)。"""
    soup = BeautifulSoup(html, "lxml")
    headings = [(h.get_text(" ", strip=True), (h.name, tuple(h.get("class") or ()))) for h in soup.select("h2, h3")]
    # The Quietus 月榜先列專輯（專輯名也加引號）再列 TRACKS
    texts = [t.upper() for t, _ in headings]
    if "TRACKS" in texts:
        headings = headings[texts.index("TRACKS") + 1:]
    elif "ALBUMS" in texts:
        return [], None  # 有專輯段卻找不到單曲段，寧可整篇不收
    parsed = [(parse_entry(t), kind) for t, kind in headings]
    # 側欄的新聞標題也常有引號（Consequence、DIY 實測），只留數量最多的那組標題樣式
    kinds = Counter(kind for e, kind in parsed if e)
    main_kind = kinds.most_common(1)[0][0] if kinds else None
    entries = [e for e, kind in parsed if e and kind == main_kind]

    nxt = soup.find("link", rel="next")
    next_url = urljoin(url, nxt["href"]) if nxt and nxt.get("href") else None
    if not next_url:
        # Rolling Stone 一頁 50 筆，下一頁網址只在頁內 JSON
        m = re.search(r'"nextPageLink":"(https?:[^"]+)"', html)
        next_url = m[1].replace("\\/", "/") if m else None
    return entries, next_url


def _find_lists(scraper, index_url: str) -> list[str]:
    resp = scraper._get(index_url)
    feed = feedparser.parse(resp.content)
    if feed.entries:
        items = [(e.get("title", ""), e.get("link", "")) for e in feed.entries]
    else:
        soup = BeautifulSoup(resp.text, "lxml")
        items = [(a.get_text(" ", strip=True), a["href"]) for a in soup.find_all("a", href=True)]
    host = urlparse(index_url).hostname.removeprefix("www.")
    urls = [urljoin(index_url, link) for title, link in items if link and is_list_title(title)]
    urls = [u for u in urls if (urlparse(u).hostname or "").removeprefix("www.") == host]
    return list(dict.fromkeys(urls))[:_MAX_LISTS]


def fetch_list_tracks(scraper) -> list[Track]:
    """擷取該來源今年的單曲榜曲目。失敗只記警告，不影響該來源的日常曲目。"""
    tracks: list[Track] = []
    for index_url in getattr(scraper, "list_index_urls", ()):
        try:
            list_urls = _find_lists(scraper, index_url)
        except Exception as e:
            logger.warning(f"{scraper.name} 榜單索引讀取失敗（{index_url}）：{e}")
            continue
        for url in list_urls:
            page, found = url, 0
            base = url.split("?")[0].rstrip("/") + "/"
            try:
                for _ in range(_MAX_PAGES):
                    entries, page = parse_list_page(scraper._get(page).text, page)
                    found += len(entries)
                    tracks += [Track(artist=a, title=t, source=scraper.name) for a, t in entries]
                    # 只跟同一篇的分頁，不跟到下一篇文章
                    if not page or not page.startswith(base):
                        break
            except Exception as e:
                logger.warning(f"{scraper.name} 榜單讀取失敗（{url}）：{e}")
            logger.info(f"{scraper.name} 榜單：{url} 找到 {found} 首")
    return tracks
