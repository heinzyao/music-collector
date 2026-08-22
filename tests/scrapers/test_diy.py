"""DIY 擷取器測試。"""

import pytest

from music_collector.scrapers.diy import DIYScraper


class TestExtractSongTitle:
    """_extract_song_title() 靜態方法測試。"""

    @pytest.mark.parametrize(
        "title, expected",
        [
            # 單一引號曲名
            ("beabadoobee shares bittersweet new single ‘Memories’", "Memories"),
            # 專輯 + 單曲雙引號：必須取單曲，不是專輯
            (
                "Jamie T returns with new album ‘Ghosts (100 Days of Morning)’ "
                "and shares single ‘3310’",
                "3310",
            ),
            # 單曲在前、專輯在後
            (
                "Remi Wolf shares new single ‘Bottle’ from forthcoming "
                "album ‘Mud’",
                "Bottle",
            ),
            # 只有專輯名 → 不是曲目，跳過
            ("Cameron Winter announces live album, ‘Live at Carnegie Hall’", None),
            # 無引號
            ("Mystery Jets: Gazing Skywards", None),
            # 所有格的直單引號不可被當成開引號
            ("Sorry's new record is out next week", None),
        ],
    )
    def test_extract(self, title, expected):
        assert DIYScraper._extract_song_title(title) == expected


class TestMatchArtistTag:
    """_match_artist_tag() 靜態方法測試。"""

    def test_takes_tag_matching_title_start(self):
        artist = DIYScraper._match_artist_tag(
            "beabadoobee shares new single ‘Memories’",
            ["News", "beabadoobee", "Watch", "A. L. Noonan"],
        )
        assert artist == "beabadoobee"

    def test_prefers_longest_match(self):
        """短藝人名是長藝人名的前綴時，必須取長的那個。"""
        artist = DIYScraper._match_artist_tag(
            "Sorry State share new single ‘Figure 8’",
            ["News", "Sorry", "Sorry State"],
        )
        assert artist == "Sorry State"

    def test_no_tag_at_title_start(self):
        """多藝人合體新聞：沒有 tag 出現在標題開頭，應放棄而非亂猜。"""
        artist = DIYScraper._match_artist_tag(
            "Porij, Picture Parlour and more join the lineup",
            ["News", "Sports Team", "Walt Disco"],
        )
        assert artist is None
