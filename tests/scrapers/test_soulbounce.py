"""SoulBounce 擷取器測試。"""

import pytest

from music_collector.scrapers import soulbounce
from music_collector.scrapers.soulbounce import SoulBounceScraper


class TestExtractSongTitle:
    """_extract_song_title() 靜態方法測試。"""

    @pytest.mark.parametrize(
        "title, expected",
        [
            ("Snoh Aalegra Contemplates Her Romantic ‘Karma’", "Karma"),
            # 專輯在前、單曲在後：取單曲
            (
                "Anderson .Paak & Cordae Set To Release Joint Album "
                "‘Heavy Is The Crown’ And Have ‘A Good Day’ Together",
                "A Good Day",
            ),
            # 單曲在前、專輯在後
            (
                "Eric Benét Sounds Like ‘Heaven’ & Announces New Album ‘We Need Everybody’",
                "Heaven",
            ),
            # 專輯字詞落在上一組引號之前，不影響後面的單曲
            ("Kehlani Announces Album ‘Crash’ With Lead Single ‘Next 2 U’", "Next 2 U"),
            # 第二組引號前有 drop → 明確是單曲
            ("Doechii Takes Us Back To Her ‘Swamp Sessions’ To Drop ‘BOMBS’", "BOMBS"),
            # 曲名內的縮寫撇號不是結尾引號
            ("Lalah Hathaway Keeps The Fire Burning In ‘Can’t Let Go’", "Can’t Let Go"),
            # 只有專輯／巡演 → 跳過
            ("NAO Offers An October Surprise With New Album ‘Autumn’", None),
            ("Freddie Jackson (1957-2026)", None),
        ],
    )
    def test_extract(self, title, expected):
        assert SoulBounceScraper._extract_song_title(title) == expected


class TestMatchArtistTag:
    """_match_artist_tag() 靜態方法測試。"""

    @pytest.mark.parametrize(
        "title, tags, expected",
        [
            # tag 去重音、小寫 → 取標題原文
            ("Mýa Has Big Fun On ‘Saturday Night’", ["Video SoulBounce", "mya"], "Mýa"),
            ("Eric Benét Sounds Like ‘Heaven’", ["Audio", "eric benet"], "Eric Benét"),
            # 標題是 NFD 組合字元
            ("My\u0301a Has Big Fun", ["mya"], "Mýa"),
            # 直撇號 tag 對彎撇號標題
            ("Sy’Rai Is Feeling Fierce", ["Sy'rai", "Sy’Rai Smith"], "Sy’Rai"),
            # tag 只是藝人名前綴、後面緊接字母 → 不算
            ("Carly Rae Jepsen Drops ‘Hi’", ["Car"], None),
            # 沒有 tag 出現在標題開頭
            ("PJ Is Taking ‘Two Steps’", ["Paris Jones", "J. Cole"], None),
        ],
    )
    def test_match(self, title, tags, expected):
        assert SoulBounceScraper._match_artist_tag(title, tags) == expected


RSS = """<?xml version="1.0"?>
<rss version="2.0"><channel><title>SoulBounce</title>
<item><title>Mýa Has Big Fun On ‘Saturday Night’</title>
  <category>Video SoulBounce</category><category>mya</category></item>
<item><title>Cleo Sol Plans 2027 ‘Gentlewoman Tour’ For North America</title>
  <category>Events</category><category>Cleo Sol</category></item>
<item><title>Victoria Monét Tunes Into R&amp;B On ‘Frequency Of Love’</title>
  <category>Reviews</category><category>Victoria Monét</category></item>
<item><title>David ‘DL’ Lawrence (1962-2026)</title>
  <category>Relax in Paradise</category><category>David Lawrence</category></item>
</channel></rss>"""


def test_fetch_tracks_skips_events_reviews_obituaries(monkeypatch):
    monkeypatch.setattr(soulbounce, "FEED_URL", RSS)
    tracks = SoulBounceScraper().fetch_tracks()
    assert [(t.artist, t.title, t.source) for t in tracks] == [
        ("Mýa", "Saturday Night", "SoulBounce"),
    ]
