"""SPIN 擷取器測試。

SPIN 改用 RSS 後與 DIY 等擷取器一致：feedparser 直接抓 URL、不經 httpx，
因此只針對解析用的靜態方法做測試，不做 respx 整合測試。
"""

import pytest

from music_collector.scrapers.spin import SpinScraper


class TestExtractTitle:
    """_extract_title() 靜態方法測試。"""

    @pytest.mark.parametrize(
        "title, expected",
        [
            (
                "Blackwater Holylight Explore Darkness on ‘Not Here Not Gone’",
                "Not Here Not Gone",
            ),
            # 曲名尾端標點須清掉（美式排版把逗號放在引號內）
            (
                "On Kelly Moran’s ‘Mirrors,’ All Is Not What It Seems",
                "Mirrors",
            ),
            # 縮寫撇號不可被當成結尾引號
            (
                "Mitski Returns With ‘Where’s My Phone?’",
                "Where’s My Phone?",
            ),
            # 無引號 → 標題沒帶作品名，無從搜尋
            ("Cornelius Keeps Things Cooking", None),
        ],
    )
    def test_extract(self, title, expected):
        assert SpinScraper._extract_title(title) == expected


class TestMatchArtistTag:
    """_match_artist_tag() 靜態方法測試。"""

    def test_artist_mid_headline(self):
        """SPIN 的藝人常出現在句中，不像 DIY 一定在句首。"""
        artist = SpinScraper._match_artist_tag(
            "Critics Are Hailing ‘The Gold Album’ as Weezer’s Return to Form",
            ["New Music", "Pushly", "weezer"],
        )
        assert artist == "Weezer"

    def test_picks_the_tag_in_the_headline(self):
        """一篇文章可能帶多個藝人 tag，只有主角會出現在標題裡。"""
        artist = SpinScraper._match_artist_tag(
            "Interpol Try to Recapture The Early Magic on ‘This Mirror Weighs a Ton’",
            ["New Music", "Reviews", "ian curtis", "interpol", "Joy Division", "r.e.m."],
        )
        assert artist == "Interpol"

    def test_ignores_accents(self):
        """tag 常寫成 ASCII，標題用重音。"""
        artist = SpinScraper._match_artist_tag(
            "Beyoncé Goes Back To The Future With Deluxe ‘B’DAY’",
            ["News", "Beyonce", "Maluma", "Pushly"],
        )
        assert artist == "Beyonce"

    def test_keeps_existing_capitalisation(self):
        """含大寫的 tag 視為原始寫法，不可被 title() 破壞。"""
        artist = SpinScraper._match_artist_tag(
            "DOMi & JD BECK’s ‘WHO ASKED?’ Doubles Down On Organized Chaos",
            ["New Music", "DOMi & JD BECK"],
        )
        assert artist == "DOMi & JD BECK"

    def test_no_artist_tag(self):
        assert (
            SpinScraper._match_artist_tag(
                "Time for Some Christmas Crack Talk", ["New Music", "Uncategorized"]
            )
            is None
        )

    def test_takes_longest_match(self):
        artist = SpinScraper._match_artist_tag(
            "Sorry State Records Turns 20", ["News", "Sorry", "Sorry State"]
        )
        assert artist == "Sorry State"
