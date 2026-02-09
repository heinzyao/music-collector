"""Consequence 擷取器測試。"""

import respx
import httpx
import pytest

from tests.conftest import load_fixture
from music_collector.scrapers.consequence import ConsequenceScraper


class TestConsequenceScraper:
    """Consequence 擷取器整合測試。"""

    @respx.mock
    def test_fetch_tracks(self):
        html = load_fixture("consequence.html")
        url = "https://consequence.net/category/cos-exclusive-features/top-song-of-the-week/"
        respx.get(url).mock(return_value=httpx.Response(200, text=html))

        scraper = ConsequenceScraper()
        tracks = scraper.fetch_tracks()

        assert len(tracks) == 3
        assert tracks[0].artist == "Poison Ruin"
        assert tracks[0].title == "Eidolon"
        assert tracks[0].source == "Consequence"


class TestParseConsequenceTitle:
    """_parse_consequence_title() 靜態方法測試。"""

    @pytest.mark.parametrize(
        "title, expected",
        [
            (
                'Heavy Song of the Week: Poison Ruin Go Medieval Mot\u00f6rhead on "Eidolon"',
                ("Poison Ruin", "Eidolon"),
            ),
            (
                'Song of the Week: Exodus\' "3111" Marks Triumphant Return',
                ("Exodus", "3111"),
            ),
            # 跳過彙整文章
            ("Staff Picks: Best Songs of the Week", None),
        ],
    )
    def test_parse_title(self, title, expected):
        result = ConsequenceScraper._parse_consequence_title(title)
        assert result == expected
