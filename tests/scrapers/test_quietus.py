"""The Quietus 擷取器測試。"""

import pytest

from music_collector.scrapers.quietus import TheQuietusScraper


class TestTheQuietusScraper:
    """The Quietus 擷取器解析測試。"""

    def test_parse_standard_title(self):
        """標準「Artist – Album」格式。"""
        result = TheQuietusScraper.parse_artist_title("Overmono \u2013 Good Lies")
        assert result == ("Overmono", "Good Lies")

    def test_parse_dash_title(self):
        result = TheQuietusScraper.parse_artist_title("Aphex Twin - Selected Ambient Works")
        assert result == ("Aphex Twin", "Selected Ambient Works")

    def test_parse_no_separator(self):
        result = TheQuietusScraper.parse_artist_title("The Quietus Guide to Electronic Music")
        assert result is None
