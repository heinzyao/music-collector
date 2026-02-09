"""The Line of Best Fit 擷取器測試。"""

import respx
import httpx
import pytest

from tests.conftest import load_fixture
from music_collector.scrapers.lineofbestfit import LineOfBestFitScraper


class TestLineOfBestFitScraper:
    """Line of Best Fit 擷取器整合測試。"""

    @respx.mock
    def test_fetch_tracks(self):
        html = load_fixture("lineofbestfit.html")
        respx.get("https://www.thelineofbestfit.com/tracks").mock(
            return_value=httpx.Response(200, text=html)
        )

        scraper = LineOfBestFitScraper()
        tracks = scraper.fetch_tracks()

        assert len(tracks) == 3
        assert tracks[0].artist == "MX LONELY"
        assert tracks[0].title == "Anesthetic"
        assert tracks[0].source == "The Line of Best Fit"


class TestParseLOBFTitle:
    """_parse_lobf_title() 靜態方法測試。"""

    @pytest.mark.parametrize(
        "title, expected",
        [
            # 動詞清單匹配
            (
                "MX LONELY numb the pain on full-intensity eruption 'Anesthetic'",
                ("MX LONELY", "Anesthetic"),
            ),
            # 動詞清單匹配（多字藝人名）
            (
                "Phoebe Bridgers shares haunting new track 'Kyoto'",
                ("Phoebe Bridgers", "Kyoto"),
            ),
            # 正規表達式（大寫藝人名）
            (
                "Phoebe Bridgers explores longing on 'Moon Song'",
                ("Phoebe Bridgers", "Moon Song"),
            ),
            # 無引號
            ("No quotes in this title at all", None),
        ],
    )
    def test_parse_title(self, title, expected):
        result = LineOfBestFitScraper._parse_lobf_title(title)
        assert result == expected
