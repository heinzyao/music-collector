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
        "title, href, expected",
        [
            # slug 定位藝人名：敘述句再長也切得準
            (
                "Yuma Koda revisits the cinema of his childhood on delicate "
                "ballad \u2018ende\u2019",
                "/tracks/yuma-koda-ende",
                ("Yuma Koda", "ende"),
            ),
            # 團名本身含 the/of，不能在第一個小寫字就停
            (
                "The Healing Power of Horses defy pop expectations on "
                "off-the-wall \u2018TOURNIQUET\u2019",
                "/tracks/the-healing-power-of-horses-tourniquet",
                ("The Healing Power of Horses", "TOURNIQUET"),
            ),
            # LOBF 的 slug 直接省略 &，不是寫成 and
            (
                "Captain Tallen & the Benevolent Entities on "
                "\u2018Spotted Lantern Fly\u2019",
                "/tracks/captain-tallen-the-benevolent-entities",
                ("Captain Tallen & the Benevolent Entities", "Spotted Lantern Fly"),
            ),
            # 重音字母在 slug 中被折成 ASCII
            (
                "Chlo\u00e9 Caillet turns up the heat on \u2018Change\u2019",
                "/tracks/chloe-caillet-change",
                ("Chlo\u00e9 Caillet", "Change"),
            ),
            # 所有格須從藝人名去掉
            (
                "Sin Clair\u2019s \u201cAffirmations #2\u201d is a considered "
                "exercise in restraint",
                "/tracks/sin-clair-affirmations-2",
                ("Sin Clair", "Affirmations #2"),
            ),
            # 兩組引號時取最後一組（曲名在句末）
            (
                "iKeda brings \u2018bubble riddim\u2019 universe to life on "
                "\u201cGo!\u201d",
                "/tracks/ikeda-go",
                ("iKeda", "Go!"),
            ),
            # 沒有 href → 退回大小寫啟發式
            (
                "Phoebe Bridgers explores longing on \u2018Moon Song\u2019",
                "",
                ("Phoebe Bridgers", "Moon Song"),
            ),
            # 無引號
            ("No quotes in this title at all", "/tracks/whatever", None),
        ],
    )
    def test_parse_title(self, title, href, expected):
        assert LineOfBestFitScraper._parse_lobf_title(title, href) == expected
