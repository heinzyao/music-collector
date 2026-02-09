"""Stereogum 擷取器測試。"""

import pytest

from music_collector.scrapers.stereogum import StereogumScraper


class TestParseStereogumTitle:
    """_parse_stereogum_title() 靜態方法測試。"""

    @pytest.mark.parametrize(
        "title, expected",
        [
            # 格式一：直接格式
            ('Radiohead \u2014 \u201cCreep\u201d', ("Radiohead", "Creep")),
            ('Bjork \u2013 \u201cArmy Of Me\u201d', ("Bjork", "Army Of Me")),
            ('FKA twigs - "Cellophane"', ("FKA twigs", "Cellophane")),
            # 格式二：公告格式
            (
                'Charli XCX Announces Album \u2014 Hear \u201cBrat\u201d',
                ("Charli XCX", "Brat"),
            ),
            (
                'Phoebe Bridgers Shares New Song \u2014 Hear \u201cMoon Song\u201d',
                ("Phoebe Bridgers", "Moon Song"),
            ),
            # 無法解析
            ("Just Some Random News Title", None),
            ("", None),
        ],
    )
    def test_parse_title(self, title, expected):
        result = StereogumScraper._parse_stereogum_title(title)
        assert result == expected
