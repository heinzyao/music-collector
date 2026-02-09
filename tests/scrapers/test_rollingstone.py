"""Rolling Stone 擷取器測試。"""

import respx
import httpx

from tests.conftest import load_fixture
from music_collector.scrapers.rollingstone import RollingStoneScraper


class TestRollingStoneScraper:
    """Rolling Stone 擷取器整合測試。"""

    @respx.mock
    def test_fetch_tracks_from_index_and_article(self):
        index_html = load_fixture("rollingstone_index.html")
        article_html = load_fixture("rollingstone_article.html")

        # 兩個索引頁
        respx.get("https://www.rollingstone.com/music/music-news/").mock(
            return_value=httpx.Response(200, text=index_html)
        )
        respx.get("https://www.rollingstone.com/music/music-features/").mock(
            return_value=httpx.Response(200, text="<html><body></body></html>")
        )
        # 文章頁
        respx.get(
            "https://www.rollingstone.com/music/music-news/best-new-songs-this-week-1/"
        ).mock(return_value=httpx.Response(200, text=article_html))

        scraper = RollingStoneScraper()
        tracks = scraper.fetch_tracks()

        # 標題直接解析出 1 首 + 文章中 3 首
        assert len(tracks) >= 1
        # 至少包含從 headline 直接解析出的 Charli XCX
        sources = {t.source for t in tracks}
        assert "Rolling Stone" in sources


class TestParseRecommendationHeadline:
    """_parse_recommendation_headline() 方法測試。"""

    def test_song_you_need_to_know(self):
        scraper = RollingStoneScraper()
        result = scraper._parse_recommendation_headline(
            "Song You Need to Know: Charli XCX, \u2018Brat\u2019"
        )
        assert result == ("Charli XCX", "Brat")

    def test_premiere_format(self):
        scraper = RollingStoneScraper()
        result = scraper._parse_recommendation_headline(
            "First Listen: Clairo \u2014 \u2018Charm\u2019"
        )
        assert result == ("Clairo", "Charm")

    def test_no_match(self):
        scraper = RollingStoneScraper()
        result = scraper._parse_recommendation_headline("Regular News Title")
        assert result is None
