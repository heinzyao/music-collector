"""Resident Advisor 擷取器測試。"""

import respx
import httpx

from tests.conftest import load_fixture
from music_collector.scrapers.residentadvisor import ResidentAdvisorScraper


class TestResidentAdvisorScraper:
    """Resident Advisor 擷取器整合測試。"""

    @respx.mock
    def test_fetch_tracks(self):
        html = load_fixture("residentadvisor.html")
        respx.get("https://ra.co/reviews/singles").mock(
            return_value=httpx.Response(200, text=html)
        )

        scraper = ResidentAdvisorScraper()
        tracks = scraper.fetch_tracks()

        assert len(tracks) == 2
        assert tracks[0].artist == "Overmono"
        assert tracks[0].title == "So U Kno"
        assert tracks[1].artist == "Caribou"
        assert tracks[1].title == "Honey"

    @respx.mock
    def test_js_detection_empty_page(self):
        html = "<html><body>short</body></html>"
        respx.get("https://ra.co/reviews/singles").mock(
            return_value=httpx.Response(200, text=html)
        )

        scraper = ResidentAdvisorScraper()
        tracks = scraper.fetch_tracks()
        assert tracks == []

    @respx.mock
    def test_deduplication(self):
        html = """<html><body>
        <div>""" + "x" * 600 + """</div>
        <article>
          <li><a href="/1">Overmono \u2013 So U Kno</a></li>
          <h3><a href="/1">Overmono \u2013 So U Kno</a></h3>
        </article>
        </body></html>"""
        respx.get("https://ra.co/reviews/singles").mock(
            return_value=httpx.Response(200, text=html)
        )

        scraper = ResidentAdvisorScraper()
        tracks = scraper.fetch_tracks()
        assert len(tracks) == 1
