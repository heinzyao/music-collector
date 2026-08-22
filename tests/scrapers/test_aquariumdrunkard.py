"""Aquarium Drunkard 擷取器測試。"""

import pytest

from music_collector.scrapers.aquariumdrunkard import AquariumDrunkardScraper


class TestParse:
    """_parse() 靜態方法測試。"""

    @pytest.mark.parametrize(
        "title, categories, expected",
        [
            # 標準「Artist :: Title」
            (
                "National Park :: Outside",
                ["National Park"],
                ("National Park", "Outside"),
            ),
            # 合體作品：藝人名是 tag 的延伸，仍應通過
            (
                "Don Cherry & Okay Temiz :: Music for Turkish Theater 1970",
                ["Don Cherry", "Jazz", "Okay Temiz"],
                ("Don Cherry & Okay Temiz", "Music for Turkish Theater 1970"),
            ),
            # 已知專欄名出現在藝人位置
            ("Transmissions :: Fred Thomas", ["Fred Thomas", "Podcast"], None),
            ("Black Rock :: The Bar-Kays at Wattstax", ["The Bar-Kays"], None),
            # 未列入黑名單的新專欄：藝人側對不上 tag，一樣要擋掉
            ("Sevens :: Some Song", ["Some Artist"], None),
            # 現場／archival 錄音的場地與年份註記
            (
                "Chet Baker :: Daybreak (Jazzhus Montmartre, Copenhagen, 1979)",
                ["Chet Baker", "Jazz"],
                None,
            ),
            # 沒有分隔符號
            ("Some Headline Without Separator", ["Whoever"], None),
        ],
    )
    def test_parse(self, title, categories, expected):
        assert AquariumDrunkardScraper._parse(title, categories) == expected
