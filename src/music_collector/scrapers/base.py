"""擷取器基礎模組：定義 Track 資料模型與 BaseScraper 抽象類別。

所有擷取器必須繼承 BaseScraper 並實作 fetch_tracks() 方法。
"""

import logging
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass

import httpx

from ..config import REQUEST_TIMEOUT, USER_AGENT

logger = logging.getLogger(__name__)


@dataclass
class Track:
    """曲目資料模型。"""
    artist: str   # 藝人名稱
    title: str    # 曲目名稱
    source: str   # 來源媒體名稱


class BaseScraper(ABC):
    """擷取器抽象基礎類別。

    提供共用的 HTTP 請求、文字解析工具方法。
    子類別需設定 name 屬性並實作 fetch_tracks()。
    """
    name: str = "base"

    @abstractmethod
    def fetch_tracks(self) -> list[Track]:
        """擷取曲目清單，回傳 Track 物件列表。"""
        ...

    def _get(self, url: str) -> httpx.Response:
        """發送 HTTP GET 請求，附帶 User-Agent 標頭與逾時設定。"""
        headers = {"User-Agent": USER_AGENT}
        resp = httpx.get(url, headers=headers, timeout=REQUEST_TIMEOUT, follow_redirects=True)
        resp.raise_for_status()
        return resp

    @staticmethod
    def parse_artist_title(text: str) -> tuple[str, str] | None:
        """解析「藝人 – 曲名」格式的文字。

        支援的分隔符號：" – "、" - "、" — "、": "
        """
        text = text.strip()
        for sep in [" – ", " - ", " — ", ": "]:
            if sep in text:
                parts = text.split(sep, 1)
                artist = parts[0].strip().strip('"').strip("'")
                title = parts[1].strip().strip('"').strip("'")
                if artist and title:
                    return artist, title
        return None

    @staticmethod
    def clean_text(text: str) -> str:
        """清理文字：移除多餘空白、HTML 實體等。"""
        text = re.sub(r"\s+", " ", text).strip()
        return text
