"""Pitchfork 擷取器測試。"""

import respx
import httpx

from tests.conftest import load_fixture
from music_collector.scrapers.pitchfork import PitchforkScraper


class TestPitchforkScraper:
    """Pitchfork 擷取器整合測試。"""

    @respx.mock
    def test_fetch_tracks(self):
        html = load_fixture("pitchfork.html")
        respx.get("https://pitchfork.com/reviews/best/tracks/").mock(
            return_value=httpx.Response(200, text=html)
        )

        scraper = PitchforkScraper()
        tracks = scraper.fetch_tracks()

        assert len(tracks) == 3
        assert tracks[0].artist == "Tate McRae"
        assert tracks[0].title == "Hard"
        assert tracks[0].source == "Pitchfork"
        assert tracks[1].artist == "Asake"
        assert "Miimii" in tracks[1].title
        assert tracks[2].artist == "Kendrick Lamar"
        assert tracks[2].title == "Not Like Us"

    @respx.mock
    def test_fetch_tracks_http_error(self):
        respx.get("https://pitchfork.com/reviews/best/tracks/").mock(
            return_value=httpx.Response(500)
        )

        scraper = PitchforkScraper()
        tracks = scraper.fetch_tracks()
        assert tracks == []

    @respx.mock
    def test_fetch_tracks_empty_page(self):
        respx.get("https://pitchfork.com/reviews/best/tracks/").mock(
            return_value=httpx.Response(200, text="<html><body></body></html>")
        )

        scraper = PitchforkScraper()
        tracks = scraper.fetch_tracks()
        assert tracks == []


class TestCleanTitle:
    """_clean_title() 方法測試。"""

    def test_remove_typographic_quotes(self):
        assert PitchforkScraper._clean_title("\u201cHard\u201d") == "Hard"

    def test_remove_regular_quotes(self):
        assert PitchforkScraper._clean_title('"Hello"') == "Hello"

    def test_preserve_ft_info(self):
        result = PitchforkScraper._clean_title('\u201cSong\u201d [ft. Someone]')
        assert "[ft. Someone]" in result

    def test_plain_text(self):
        assert PitchforkScraper._clean_title("Plain Title") == "Plain Title"
