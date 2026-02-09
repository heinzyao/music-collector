"""Slant Magazine 擷取器測試。"""

import respx
import httpx
import pytest

from tests.conftest import load_fixture
from music_collector.scrapers.slant import SlantScraper


class TestSlantScraper:
    """Slant 擷取器整合測試。"""

    @respx.mock
    def test_fetch_tracks(self):
        html = load_fixture("slant.html")
        respx.get("https://www.slantmagazine.com/music/").mock(
            return_value=httpx.Response(200, text=html)
        )

        scraper = SlantScraper()
        tracks = scraper.fetch_tracks()

        # "Best of 2025" 應被過濾
        assert len(tracks) == 2
        assert tracks[0].artist == "FKA twigs"
        assert tracks[0].title == "Eusexua Afterglow"
        assert tracks[1].artist == "Clairo"
        assert tracks[1].title == "Charm"

    @respx.mock
    def test_cloudflare_detection(self):
        html = "<html><body>Just a moment... Checking your browser before accessing. Enable JavaScript and cookies to continue. Cloudflare</body></html>"
        respx.get("https://www.slantmagazine.com/music/").mock(
            return_value=httpx.Response(200, text=html)
        )
        respx.get("https://www.slantmagazine.com/category/music/").mock(
            return_value=httpx.Response(200, text=html)
        )

        scraper = SlantScraper()
        tracks = scraper.fetch_tracks()
        assert tracks == []


class TestParseSlantTitle:
    """_parse_slant_title() 靜態方法測試。"""

    @pytest.mark.parametrize(
        "title, expected",
        [
            (
                "FKA twigs \u2018Eusexua Afterglow\u2019 Review: Basking",
                ("FKA twigs", "Eusexua Afterglow"),
            ),
            (
                'Radiohead "OK Computer" Review: Still Ahead of Its Time',
                ("Radiohead", "OK Computer"),
            ),
            ("Artist \u2013 Album Title", ("Artist", "Album Title")),
            ("Just some random text", None),
        ],
    )
    def test_parse_title(self, title, expected):
        result = SlantScraper._parse_slant_title(title)
        assert result == expected
