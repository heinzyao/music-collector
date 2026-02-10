"""擷取器基礎模組：定義 Track 資料模型與 BaseScraper 抽象類別。

所有擷取器必須繼承 BaseScraper 並實作 fetch_tracks() 方法。
"""

import logging
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass

import httpx

from ..config import ENABLE_PLAYWRIGHT, REQUEST_TIMEOUT, USER_AGENT

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

    _JS_BLOCK_INDICATORS = (
        "enable javascript",
        "checking your browser",
        "just a moment",
        "cloudflare",
    )

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

    def _get_rendered(self, url: str, wait_selector: str = "body") -> str | None:
        """使用 Playwright 取得 JS 渲染後的頁面 HTML。

        需安裝 playwright 可選依賴（uv sync --extra browser）
        並設定 ENABLE_PLAYWRIGHT=true 環境變數。
        回傳 HTML 字串，或 None（Playwright 未安裝/未啟用/失敗時）。
        """
        if not ENABLE_PLAYWRIGHT:
            return None

        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            logger.debug("Playwright 未安裝，跳過 JS 渲染。安裝：uv sync --extra browser")
            return None

        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(
                    headless=True,
                    args=["--disable-blink-features=AutomationControlled"],
                )
                context = browser.new_context(
                    user_agent=USER_AGENT,
                    viewport={"width": 1280, "height": 720},
                )
                page = context.new_page()

                # 隱藏 webdriver 特徵
                page.add_init_script(
                    "Object.defineProperty(navigator, 'webdriver', {get: () => false})"
                )

                page.goto(url, wait_until="domcontentloaded", timeout=30000)

                try:
                    page.wait_for_selector(wait_selector, timeout=10000)
                except Exception:
                    logger.debug(f"等待選擇器 {wait_selector} 逾時，繼續擷取")

                # 等待網路靜止（React/Next.js hydration）
                try:
                    page.wait_for_load_state("networkidle", timeout=5000)
                except Exception:
                    pass

                html = page.content()
                page.close()
                context.close()
                browser.close()
                return html

        except Exception as e:
            logger.warning(f"Playwright 渲染失敗 {url}：{e}")
            return None

    @staticmethod
    def _is_js_blocked(text: str) -> bool:
        """檢查頁面是否被 JS 渲染 / Cloudflare 挑戰阻擋。"""
        lower = text.lower()
        return any(ind in lower for ind in BaseScraper._JS_BLOCK_INDICATORS)

    @staticmethod
    def _extract_artist_before_verb(prefix: str, verb_pattern: re.Pattern[str]) -> str:
        """從標題前綴中提取藝人名，遇到第一個動詞即截斷。

        逐字掃描 prefix（跳過第一個字），遇到符合 verb_pattern 的單字時，
        取該字之前的所有文字作為藝人名。

        Args:
            prefix: 標題中引號前的文字。
            verb_pattern: 已編譯的動詞正規表達式（用於 fullmatch）。
        """
        words = prefix.split()
        if not words:
            return prefix

        for i in range(1, len(words)):
            clean_word = re.sub(r"[^\w'-]", "", words[i])
            if verb_pattern.fullmatch(clean_word):
                candidate = " ".join(words[:i]).strip()
                if candidate:
                    return candidate

        return prefix

    @staticmethod
    def _deduplicate_tracks(tracks: list[Track]) -> list[Track]:
        """以 (artist, title) 大小寫不敏感去重。"""
        seen: set[tuple[str, str]] = set()
        unique: list[Track] = []
        for t in tracks:
            key = (t.artist.lower(), t.title.lower())
            if key not in seen:
                seen.add(key)
                unique.append(t)
        return unique

    @staticmethod
    def clean_text(text: str) -> str:
        """清理文字：移除多餘空白、HTML 實體等。"""
        text = re.sub(r"\s+", " ", text).strip()
        return text
