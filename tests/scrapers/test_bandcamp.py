"""Bandcamp Daily 擷取器測試。"""

import pytest

from music_collector.scrapers.bandcamp import BandcampDailyScraper


class TestParseBandcampTitle:
    """_parse_bandcamp_title() 靜態方法測試。"""

    @pytest.mark.parametrize(
        "title, expected",
        [
            # 逗號 + 雙引號
            (
                'Waxahatchee, "Tigers Blood"',
                ("Waxahatchee", "Tigers Blood"),
            ),
            # 逗號 + typographic 引號
            (
                "Clairo, \u201cCharm\u201d",
                ("Clairo", "Charm"),
            ),
            # 逗號 + 單引號
            (
                "MJ Lenderman, \u2018Manning Fireworks\u2019",
                ("MJ Lenderman", "Manning Fireworks"),
            ),
            # Dash 格式（備選）
            (
                "Radiohead \u2013 OK Computer",
                ("Radiohead", "OK Computer"),
            ),
            # 無法解析
            ("Essential Releases, Feb 6", None),
            ("", None),
        ],
    )
    def test_parse_title(self, title, expected):
        result = BandcampDailyScraper._parse_bandcamp_title(title)
        assert result == expected
