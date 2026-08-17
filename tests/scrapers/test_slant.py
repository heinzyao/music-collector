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

    @pytest.mark.parametrize(
        "title, expected",
        [
            # \u683c\u5f0f 1\uff1aArtist \u2018Title\u2019 Review: \u2026 \u2014\u2014 \u85dd\u4eba\u5728\u5f15\u865f\u524d
            (
                "Ravyn Lenae \u2018Blue Island\u2019 Review: Pop Ambition That Lacks Conviction",
                ("Ravyn Lenae", "Blue Island"),
            ),
            (
                "Open Mike Eagle & Kenny Segal \u2018Doomed!\u2019 Review: A Soundtrack for the Brokenhearted",
                ("Open Mike Eagle & Kenny Segal", "Doomed!"),
            ),
            # \u683c\u5f0f 2\uff1aReview: With \u2018Title,\u2019 Artist <\u52d5\u8a5e> \u2014\u2014 \u85dd\u4eba\u5728\u5f15\u865f\u4e4b\u5f8c\uff0c
            # \u4e14\u7f8e\u5f0f\u6392\u7248\u628a\u9017\u865f\u653e\u5728\u5f15\u865f\u5167
            (
                "Review: With \u2018Hazel Eyes,\u2019 Sam Smith Finds Freedom in Imperfection",
                ("Sam Smith", "Hazel Eyes"),
            ),
            (
                "Review: With \u2018Therapy at the Club,\u2019 Flo Swings Big but Falls Short",
                ("Flo", "Therapy at the Club"),
            ),
            (
                "Review: With \u2018XXXXX,\u2019 Arca Serves Up Controlled Chaos",
                ("Arca", "XXXXX"),
            ),
            # \u683c\u5f0f 3\uff1aReview: Artist\u2019s \u2018Title\u2019 <\u52d5\u8a5e> \u2014\u2014 \u85dd\u4eba\u5728\u5f15\u865f\u524d\u4f46\u5e36\u6240\u6709\u683c
            (
                "Review: Icona Pop\u2019s \u2018Ritual\u2019 Is Preoccupied with Change but Offers Nothing New",
                ("Icona Pop", "Ritual"),
            ),
            # \u627e\u4e0d\u5230\u52d5\u8a5e\u908a\u754c\u6642\u5be7\u53ef\u653e\u68c4\uff0c\u4e5f\u4e0d\u8981\u5beb\u5165\u6574\u53e5\u5783\u573e
            # \uff08DB \u7684 UNIQUE(artist,title) \u6703\u8b93\u721b\u8cc7\u6599\u6c38\u4e45\u7559\u5b58\uff09
            ("Review: With \u2018Some Song,\u2019 " + " ".join(["Word"] * 8), None),
        ],
    )
    def test_parse_real_slant_headlines(self, title, expected):
        assert SlantScraper._parse_slant_title(title) == expected


class TestShouldSkip:
    """_should_skip() 只應比對引號外的文字。"""

    @pytest.mark.parametrize(
        "text",
        [
            # 曲名裡出現跳過詞不該被誤殺
            "Charli XCX ‘Music, Fashion, Film’ Review: Flex, Fuzz, and Fractured Ego",
            "Someone ‘TV Party’ Review: A Racket Worth Making",
            "Someone ‘The Best of Both Worlds’ Review: Split Down the Middle",
        ],
    )
    def test_keeps_music_reviews_with_skip_words_in_title(self, text):
        assert SlantScraper._should_skip(text) is False

    @pytest.mark.parametrize(
        "text",
        [
            # 引號外出現跳過詞，代表真的是非音樂內容
            "The 25 Best Albums of 2026, Ranked",
            "Interview: Someone on Their New Record",
            "Wes Anderson ‘Isle of Dogs’ Film Review: Stop-Motion Splendor",
        ],
    )
    def test_skips_non_music_content(self, text):
        assert SlantScraper._should_skip(text) is True
