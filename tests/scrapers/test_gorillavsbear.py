"""Gorilla vs. Bear 擷取器測試。"""

import pytest

from music_collector.scrapers.gorillavsbear import GorillaVsBearScraper


class TestGorillaVsBearScraper:
    """Gorilla vs. Bear 擷取器解析測試。"""

    def test_parse_standard_title(self):
        """標準「Artist – Title」格式。"""
        result = GorillaVsBearScraper.parse_artist_title("Waxahatchee \u2013 Tigers Blood")
        assert result == ("Waxahatchee", "Tigers Blood")

    def test_parse_dash_title(self):
        result = GorillaVsBearScraper.parse_artist_title("Clairo - Charm")
        assert result == ("Clairo", "Charm")

    def test_parse_no_separator(self):
        result = GorillaVsBearScraper.parse_artist_title("Just A Post Title")
        assert result is None
