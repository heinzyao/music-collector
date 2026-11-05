"""年度／月度單曲榜解析測試。範例取自各站 2025 年度榜實際標題。"""

from datetime import date

import pytest

from music_collector.scrapers.lists import is_list_title, parse_entry, parse_list_page


@pytest.mark.parametrize(
    "text, expected",
    [
        ('Lorde - "Man Of The Year" (Universal)', ("Lorde", "Man Of The Year")),
        ("Tame Impala — “Dracula”", ("Tame Impala", "Dracula")),
        ("Morgan Wallen / Post Malone: “I Ain’t Comin’ Back”", ("Morgan Wallen / Post Malone", "I Ain’t Comin’ Back")),
        ("Mark Ernestus’ Ndagga Rhythm Force: “Lamp Fall”", ("Mark Ernestus’ Ndagga Rhythm Force", "Lamp Fall")),
        ("Miley Cyrus, ‘End of the World’", ("Miley Cyrus", "End of the World")),
        ("Sunn O))) ‘Eternity’s Pillars’ Sub Pop", ("Sunn O)))", "Eternity’s Pillars")),
        ("Lifeloose ’07XXXXXXXXX’ 193bpm", ("Lifeloose", "07XXXXXXXXX")),
        ("20. Westside Cowboy — Shells", ("Westside Cowboy", "Shells")),
        ("18. Model/​Actriz — Diva", ("Model/Actriz", "Diva")),
        # 沒有名次編號、也沒有引號：不是榜單項目
        ("Wolf Alice - Play It Out", None),
        ("From the Archive", None),
    ],
)
def test_parse_entry(text, expected):
    assert parse_entry(text) == expected


@pytest.mark.parametrize(
    "title, today, expected",
    [
        ("The 100 Best Songs of 2025", date(2025, 12, 5), True),
        ("The 40 Best Rap Songs of 2025", date(2025, 12, 5), True),
        ("DIY's 2025 Tracks of the Year", date(2025, 12, 5), True),
        ("Music of the Month: The Best Albums and Tracks of October 2026", date(2026, 11, 1), True),
        ("The 50 Best Albums of 2025", date(2025, 12, 5), False),        # 專輯榜不收
        ("Staff Picks: Best Albums of October 2026", date(2026, 11, 1), False),
        ("The 5 Best Songs Of The Week", date(2026, 11, 1), False),      # 週榜不在範圍
        ("The 200 Best Songs of the 2020s", date(2026, 11, 1), False),
        ("The Best Songs of 2016", date(2026, 11, 1), False),            # 索引頁上的舊榜
        ("The 100 Best Songs of 2025", date(2026, 1, 10), False),        # 跨年才出的去年年終榜也不收
        ("The 100 Best Songs of 2025", date(2026, 2, 10), False),
        ("Pink Floyd Box Set With Previously Unreleased Tracks", date(2026, 11, 1), False),
    ],
)
def test_is_list_title(title, today, expected):
    assert is_list_title(title, today) is expected


def test_parse_list_page_skips_sidebar_and_albums():
    html = """
    <h2>ALBUMS</h2><h2>@ ‘Autosmile’ 4AD</h2>
    <h2>TRACKS</h2>
    <h2 class="entry">Tresque ‘Faï Anar’ zamzamrec</h2>
    <h2 class="entry">Anna Meredith ‘Dusky’ Mercury KX</h2>
    <h3 class="headline">RAYE wins Mercury Prize for ‘THIS MUSIC’</h3>
    """
    entries, nxt = parse_list_page(html, "https://example.com/list/")
    assert entries == [("Tresque", "Faï Anar"), ("Anna Meredith", "Dusky")]
    assert nxt is None


def test_parse_list_page_next_page():
    url = "https://www.rollingstone.com/music/music-lists/best-songs-of-2025-1/"
    html = '<h2>Lady Gaga, ‘Abracadabra’</h2><script>var x = {"nextPageLink":"https:\\/\\/www.rollingstone.com\\/music\\/music-lists\\/best-songs-of-2025-1\\/foo-2"};</script>'
    _, nxt = parse_list_page(html, url)
    assert nxt == url + "foo-2"
    html = '<link rel="next" href="/list/2/"><h2>A ‘B’</h2>'
    assert parse_list_page(html, "https://thequietus.com/list/")[1] == "https://thequietus.com/list/2/"


def test_parse_list_page_albums_without_tracks_section():
    html = "<h2>ALBUMS</h2><h2>@ ‘Autosmile’ 4AD</h2><h2>Gnod ‘Chronicles’ Rocket</h2>"
    assert parse_list_page(html, "https://example.com/list/") == ([], None)


def test_weekly_lists_skipped():
    assert not is_list_title("Best New Songs This Week – 2026", date(2026, 11, 6))
