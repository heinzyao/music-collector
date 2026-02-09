"""Complex 擷取器測試。"""

import respx
import httpx

from tests.conftest import load_fixture
from music_collector.scrapers.complex import ComplexScraper


class TestComplexScraper:
    """Complex 擷取器整合測試。"""

    @respx.mock
    def test_fetch_tracks(self):
        html = load_fixture("complex.html")
        respx.get("https://www.complex.com/music").mock(
            return_value=httpx.Response(200, text=html)
        )

        scraper = ComplexScraper()
        tracks = scraper.fetch_tracks()

        assert len(tracks) >= 2
        assert tracks[0].source == "Complex"

    @respx.mock
    def test_js_detection(self):
        html = "<html><body>Just a moment... enable javascript cloudflare</body></html>"
        respx.get("https://www.complex.com/music").mock(
            return_value=httpx.Response(200, text=html)
        )

        scraper = ComplexScraper()
        tracks = scraper.fetch_tracks()
        assert tracks == []

    @respx.mock
    def test_empty_body_js_detection(self):
        html = "<html><body>short</body></html>"
        respx.get("https://www.complex.com/music").mock(
            return_value=httpx.Response(200, text=html)
        )

        scraper = ComplexScraper()
        tracks = scraper.fetch_tracks()
        assert tracks == []

    @respx.mock
    def test_all_urls_fail(self):
        respx.get("https://www.complex.com/music").mock(side_effect=Exception("fail"))
        respx.get("https://www.complex.com/tag/best-new-music").mock(
            side_effect=Exception("fail")
        )
        respx.get("https://www.complex.com/pigeons-and-planes").mock(
            side_effect=Exception("fail")
        )

        scraper = ComplexScraper()
        tracks = scraper.fetch_tracks()
        assert tracks == []
