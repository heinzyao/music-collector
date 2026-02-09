"""SPIN 擷取器測試。"""

import respx
import httpx
import pytest

from tests.conftest import load_fixture
from music_collector.scrapers.spin import SpinScraper


class TestSpinScraper:
    """SPIN 擷取器整合測試。"""

    @respx.mock
    def test_fetch_tracks(self):
        html = load_fixture("spin.html")
        respx.get("https://www.spin.com/new-music/").mock(
            return_value=httpx.Response(200, text=html)
        )

        scraper = SpinScraper()
        tracks = scraper.fetch_tracks()

        assert len(tracks) == 3
        assert tracks[0].artist == "Blackwater Holylight"
        assert tracks[0].title == "Not Here Not Gone"
        assert tracks[0].source == "SPIN"


class TestParseSpinTitle:
    """_parse_spin_title() 靜態方法測試。"""

    @pytest.mark.parametrize(
        "title, expected",
        [
            (
                "Blackwater Holylight Explore Darkness on \u2018Not Here Not Gone\u2019",
                ("Blackwater Holylight", "Not Here Not Gone"),
            ),
            (
                "Cat Power Takes Us Back In Time With New EP \u2018Redux\u2019",
                ("Cat Power", "Redux"),
            ),
            (
                "On Kelly Moran\u2019s \u2018Mirrors,\u2019 All Is Not What It Seems",
                ("Kelly Moran", "Mirrors"),
            ),
            # 跳過非音樂內容
            ("Artist Dies at 75", None),
            ("Tour Announced for Artist", None),
            # 無引號
            ("Just A Normal Headline Without Quotes", None),
        ],
    )
    def test_parse_title(self, title, expected):
        result = SpinScraper._parse_spin_title(title)
        assert result == expected
