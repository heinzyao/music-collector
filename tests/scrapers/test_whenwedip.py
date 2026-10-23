"""When We Dip 擷取器測試。"""

import pytest

from music_collector.scrapers import whenwedip
from music_collector.scrapers.whenwedip import WhenWeDipScraper


@pytest.mark.parametrize(
    "title, expected",
    [
        ("The Reactivitz brings bright, groovy tech house to There Is A Light via ‘Eyes Low’", "Eyes Low"),
        # EP／合輯寫在引號後 → 跳過
        ("Luc Angenehm explores deeper shades across four-track ‘Malone’ EP via Bespoke Musik", None),
        ("All Day I Dream bids farewell with stunning 13-track ‘Summer’s End Sampler’ VA", None),
        # 專輯寫在引號前
        ("Mariano Mellino unveils his new album ‘CONTACTO’ on Audioholics Records", None),
        # remix 不是 mix：曲名照收
        ("Matthew Sona ventures into the beyond with his remix of Artic White’s ‘Aldilá’", "Aldilá"),
        # 引號前的 mix 是形容曲風，不是 DJ mix
        ("Kepler delivers a hypnotic mix of house and techno on ‘Inner Motion’", "Inner Motion"),
        # 曲名內的縮寫撇號不是結尾引號
        ("Tim Parelias delivers melodic layering with ‘Don’t Be Afraid, Honey’", "Don’t Be Afraid, Honey"),
    ],
)
def test_extract_song_title(title, expected):
    assert WhenWeDipScraper._extract_song_title(title) == expected


RSS = """<?xml version="1.0"?>
<rss version="2.0"><channel><title>When We Dip</title>
<item><title>Premiere: Collé keeps it close and emotive with ‘Hold Me Closer’ on MINDGAME Records</title>
  <category>House</category><category>News</category><category>Premieres</category><category>Collé</category></item>
<item><title>Peer Kusiv returns to Forevermore with soulful melodic house gem, ‘Grateful’</title>
  <category>Melodic House</category><category>Reviews</category><category>Peer Kusiv</category></item>
<item><title>Little Talk with Caetano Malta about ‘Saudade’</title>
  <category>House</category><category>Interviews</category><category>Caetano Malta</category></item>
<item><title>Premiere: Label boss Peter Makto takes Artic White’s ‘Simmetry’ into the early hours</title>
  <category>Premieres</category><category>Artic White</category></item>
</channel></rss>"""


def test_fetch_tracks_keeps_reviews_and_premieres(monkeypatch):
    monkeypatch.setattr(whenwedip, "FEED_URL", RSS)
    tracks = WhenWeDipScraper().fetch_tracks()
    # 專訪跳過；標題開頭對不上 tag（Label boss …）時放棄而非亂猜
    assert [(t.artist, t.title, t.source) for t in tracks] == [
        ("Collé", "Hold Me Closer", "When We Dip"),
        ("Peer Kusiv", "Grateful", "When We Dip"),
    ]
