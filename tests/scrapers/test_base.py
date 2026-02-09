"""BaseScraper 基礎方法測試。"""

import pytest

from music_collector.scrapers.base import BaseScraper, Track


class TestParseArtistTitle:
    """parse_artist_title() 靜態方法測試。"""

    @pytest.mark.parametrize(
        "text, expected",
        [
            ("Artist – Song Title", ("Artist", "Song Title")),
            ("Artist - Song Title", ("Artist", "Song Title")),
            ("Artist — Song Title", ("Artist", "Song Title")),
            ("Artist: Song Title", ("Artist", "Song Title")),
            ('  "Artist" – "Title"  ', ("Artist", "Title")),
            ("'Artist' – 'Title'", ("Artist", "Title")),
            ("Only Text Without Separator", None),
            ("", None),
            (" – Title Only", None),
            ("Artist – ", None),
        ],
    )
    def test_parse_artist_title(self, text, expected):
        result = BaseScraper.parse_artist_title(text)
        assert result == expected


class TestCleanText:
    """clean_text() 靜態方法測試。"""

    @pytest.mark.parametrize(
        "text, expected",
        [
            ("  hello   world  ", "hello world"),
            ("line\n\nbreak", "line break"),
            ("tab\there", "tab here"),
            ("normal text", "normal text"),
            ("", ""),
        ],
    )
    def test_clean_text(self, text, expected):
        result = BaseScraper.clean_text(text)
        assert result == expected


class TestTrackDataclass:
    """Track 資料模型測試。"""

    def test_track_creation(self):
        t = Track(artist="Radiohead", title="Creep", source="Test")
        assert t.artist == "Radiohead"
        assert t.title == "Creep"
        assert t.source == "Test"

    def test_track_equality(self):
        t1 = Track(artist="A", title="B", source="S")
        t2 = Track(artist="A", title="B", source="S")
        assert t1 == t2
