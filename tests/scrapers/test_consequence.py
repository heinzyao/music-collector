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

        assert len(tracks) == 4
        assert tracks[0].artist == "Poison Ruin"
        assert tracks[0].title == "Eidolon"
        assert tracks[0].source == "Consequence"
        # 動詞 "Show" 不在 _VERB_PATTERNS 內，只有 URL slug 能切出藝人名
        assert tracks[3].artist == "Fake Names"
        assert tracks[3].title == "Until It's Normal"


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

    @pytest.mark.parametrize(
        "title, href, expected",
        [
            # 動詞不在清單內，靠 slug 切出藝人名
            (
                'Heavy Song of the Week: Fake Names Show Power Pop Mastery on "Until It\'s Normal"',
                "https://consequence.net/2026/09/heavy-song-of-the-week-fake-names-until-its-normal/",
                ("Fake Names", "Until It's Normal"),
            ),
            (
                'Heavy Song of the Week: Sigh Transform into Melodic Folk Metal Magicians on "Unputenpu"',
                "https://consequence.net/2026/07/heavy-song-of-the-week-sigh-unputenpu/",
                ("Sigh", "Unputenpu"),
            ),
            # 所有格開頭
            (
                'Heavy Song of the Week: Godflesh\'s Farewell Starts with the Thrilling "Living/Ending"',
                "https://consequence.net/2026/08/heavy-song-of-the-week-godflesh-living-ending/",
                ("Godflesh", "Living/Ending"),
            ),
            # slug 格式不符 → 退回動詞清單
            (
                'Heavy Song of the Week: Mastodon Get Feral Again with "Barbarians Blood"',
                "/some/unrelated/path/",
                ("Mastodon", "Barbarians Blood"),
            ),
        ],
    )
    def test_parse_title_with_slug(self, title, href, expected):
        assert ConsequenceScraper._parse_consequence_title(title, href) == expected
