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
            # 專輯名裡的撇號不可提早收尾（曾被截成 "Can"）
            (
                "Various Artists, \u201cCan\u2019t Stop It! II: "
                "Australian Post Punk 1979\u201384\u201d (2026 Deluxe Edition)",
                (
                    "Various Artists",
                    "Can\u2019t Stop It! II: Australian Post Punk 1979\u201384",
                ),
            ),
            # 團名含逗號時須完整保留
            (
                "Henry Threadgill, Vijay Iyer & Dafnis Prieto, \u201cFifteen\u201d",
                ("Henry Threadgill, Vijay Iyer & Dafnis Prieto", "Fifteen"),
            ),
            # 無引號 → 不解析。沒有 dash 備選，散文標題不會被切成假曲目
            ("Essential Releases, Feb 6", None),
            ("Radiohead \u2013 OK Computer", None),
            ("Spit-Polished: A Guide to Shit & Shine", None),
            ("", None),
        ],
    )
    def test_parse_title(self, title, expected):
        result = BandcampDailyScraper._parse_bandcamp_title(title)
        assert result == expected
