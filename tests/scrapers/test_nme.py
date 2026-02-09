"""NME 擷取器測試。"""

import respx
import httpx
import pytest

from tests.conftest import load_fixture
from music_collector.scrapers.nme import NMEScraper


class TestNMEScraper:
    """NME 擷取器整合測試。"""

    @respx.mock
    def test_fetch_tracks(self):
        html = load_fixture("nme.html")
        respx.get("https://www.nme.com/reviews/track").mock(
            return_value=httpx.Response(200, text=html)
        )

        scraper = NMEScraper()
        tracks = scraper.fetch_tracks()

        assert len(tracks) == 3
        assert tracks[0].artist == "Harry Styles"
        assert tracks[0].title == "Aperture"
        assert tracks[0].source == "NME"

    @respx.mock
    def test_fetch_tracks_empty(self):
        respx.get("https://www.nme.com/reviews/track").mock(
            return_value=httpx.Response(200, text="<html><body></body></html>")
        )

        scraper = NMEScraper()
        tracks = scraper.fetch_tracks()
        assert tracks == []


class TestParseNMETitle:
    """_parse_nme_review_title() 靜態方法測試。"""

    @pytest.mark.parametrize(
        "title, expected_artist, expected_title",
        [
            # 模式 C：所有格 + 引號
            (
                "Mitski\u2019s new single \u2018Where\u2019s My Phone?\u2019",
                "Mitski",
                "Where\u2019s My Phone?",
            ),
            # 模式 A：Is 開頭
            (
                "Is \u2018Opening Night\u2019 a curtain call for Arctic Monkeys?",
                "Arctic Monkeys",
                "Opening Night",
            ),
            # 模式 C：動詞 + on + 引號
            (
                "Harry Styles takes things slow on \u2018Aperture\u2019",
                "Harry Styles",
                "Aperture",
            ),
        ],
    )
    def test_parse_title(self, title, expected_artist, expected_title):
        result = NMEScraper._parse_nme_review_title(title)
        assert result is not None
        assert result[0] == expected_artist
        assert result[1] == expected_title

    def test_skip_interview(self):
        result = NMEScraper._parse_nme_review_title("Interview with Radiohead")
        assert result is None
