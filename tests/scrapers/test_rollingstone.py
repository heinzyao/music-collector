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

        assert len(tracks) >= 1
        sources = {t.source for t in tracks}
        assert "Rolling Stone" in sources

        pairs = {(t.artist, t.title) for t in tracks}
        # 藝人名含逗號時不可被截斷成 "Creator"
        assert ("AZ Chike feat. Tyler, the Creator", "Look Like My Mama") in pairs
        # 段尾常被接上側欄的 Trending Stories 文字，不可污染曲名
        assert ("Angela Autumn", "I Don\u2019t Think About You At All") in pairs


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

    def test_skips_film_news_with_quoted_words(self):
        """影劇新聞會命中 Debut/Premiere 關鍵詞，但藝人名含引號，應被擋下。"""
        scraper = RollingStoneScraper()
        result = scraper._parse_recommendation_headline(
            "Phoebe Bridgers Talks \u2018Super Intimidating\u2019 Acting Debut "
            "at \u2018Primetime\u2019 Venice Premiere"
        )
        assert result is None

    def test_premieres_new_song_still_parses(self):
        scraper = RollingStoneScraper()
        result = scraper._parse_recommendation_headline(
            "Beyonc\u00e9 Premieres New Song \u2018Cozy\u2019"
        )
        assert result == ("Beyonc\u00e9", "Cozy")
