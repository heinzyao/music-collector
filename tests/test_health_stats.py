"""來源新鮮度（stale）、配對率與採用率測試。全部使用記憶體 SQLite，不打網路。"""

from unittest.mock import MagicMock

import pytest

from music_collector import db, stats
from music_collector.health import (
    get_health_report,
    get_source_health,
    get_unhealthy_sources,
    record_scrape_result,
)


@pytest.fixture
def conn(monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", ":memory:")
    c = db.init_db()
    yield c
    c.close()


def _add(conn, artist, source, days_ago, uri=None):
    conn.execute(
        "INSERT INTO tracks (artist, title, source, spotify_uri, added_at) "
        "VALUES (?, 't', ?, ?, datetime('now', ?))",
        (artist, source, uri, f"-{days_ago} days"),
    )


def test_recent_new_track_is_healthy(conn):
    _add(conn, "a", "SPIN", 2)
    record_scrape_result(conn, "SPIN", 10)
    h = get_source_health(conn, "SPIN")
    assert h.status == "healthy"
    assert h.days_since_new == 2


def test_old_tracks_only_is_stale_even_when_scrape_returns_tracks(conn):
    _add(conn, "a", "NME", 60)
    record_scrape_result(conn, "NME", 12)
    h = get_source_health(conn, "NME")
    assert h.status == "stale"
    assert h.days_since_new == 60

    report = get_health_report(conn, ["NME"])
    assert "最後新曲目：" in report and "（60 天前）" in report
    assert "60 天沒有新曲目（可能停更、抓到舊頁，或曲目都被其他來源先收錄）" in report


def test_never_had_tracks_is_stale(conn):
    record_scrape_result(conn, "RA", 5)
    h = get_source_health(conn, "RA")
    assert h.status == "stale"
    assert h.days_since_new is None
    assert "最後新曲目：無" in get_health_report(conn, ["RA"])


def test_failure_and_empty_take_precedence_over_stale(conn):
    for _ in range(3):
        record_scrape_result(conn, "X", 0, error="boom")
    assert get_source_health(conn, "X").status == "unhealthy"

    for d in range(5):
        conn.execute(
            "INSERT INTO source_checks (source, status, track_count, checked_at) "
            "VALUES ('Y', 'empty', 0, datetime('now', ?))",
            (f"-{d} days",),
        )
    assert get_source_health(conn, "Y").status == "warning"


def test_unhealthy_sources_include_stale(conn):
    _add(conn, "a", "Fresh", 1)
    _add(conn, "b", "Old", 31)
    record_scrape_result(conn, "Fresh", 3)
    record_scrape_result(conn, "Old", 3)
    assert [h.source for h in get_unhealthy_sources(conn, ["Fresh", "Old"])] == ["Old"]


def test_show_sources_prints_match_rate(conn, monkeypatch, capsys):
    _add(conn, "a", "S", 1, "spotify:track:1")
    _add(conn, "b", "S", 1, "spotify:track:2")
    _add(conn, "c", "S", 1, "spotify:track:3")
    _add(conn, "d", "S", 1, None)
    monkeypatch.setattr(stats, "init_db", lambda: conn)
    stats.show_sources()
    out = capsys.readouterr().out
    assert "配對率" in out
    line = next(ln for ln in out.splitlines() if ln.strip().startswith("S "))
    assert line.split()[1:4] == ["4", "3", "75%"]


def _playlist(pid, name, owner="me"):
    return {"id": pid, "name": name, "owner": {"id": owner}}


def test_own_playlist_track_ids_excludes_generated_and_paginates(monkeypatch):
    monkeypatch.setattr(stats, "ALL_TIME_PLAYLIST_NAME", "Custom All Time")
    sp = MagicMock()
    sp.current_user.return_value = {"id": "me"}
    pages = {
        "playlists-2": {"items": [_playlist("p2", "Mine 2")], "next": None},
        "p1-2": {"items": [{"track": {"uri": "u:B", "id": "B"}}], "next": None},  # 舊 app 的 track 鍵
    }
    sp.next.side_effect = lambda r: pages[r["next"]]
    sp.current_user_playlists.side_effect = lambda limit, offset: pages["playlists-2"] if offset else {
        "items": [
            _playlist("p1", "Mine"),
            _playlist("cp", "Critics' Picks — All Time"),
            _playlist("ft", "Fresh Tracks"),
            _playlist("cfg", "Custom All Time"),
            _playlist("other", "Followed", owner="someone"),
            None,
        ],
        "next": "playlists-2",
    }
    sp._get.side_effect = lambda path, **kw: {
        "p1": {
            "items": [{"item": {"uri": "u:A", "id": "A"}}, {"item": None}, {"item": {"uri": "u:x", "id": None}}],
            "next": "p1-2",
        },
        "p2": {"items": [{"item": {"uri": "u:C", "id": "C"}}], "next": None},
    }[path.split("/")[1]]

    assert stats.own_playlist_track_ids(sp) == {"A", "B", "C"}
    assert sorted(c.args[0] for c in sp._get.call_args_list) == ["playlists/p1/items", "playlists/p2/items"]


def test_compute_adoption_sorts_by_rate(conn):
    _add(conn, "a1", "Low", 1, "spotify:track:1")
    _add(conn, "a2", "Low", 1, "spotify:track:2")
    _add(conn, "a3", "Low", 1, "spotify:track:3")
    _add(conn, "a4", "Low", 1, "spotify:track:4")
    _add(conn, "b1", "High", 1, "spotify:track:5")
    _add(conn, "b2", "High", 1, "spotify:track:6")
    _add(conn, "c1", "Zero", 1, "spotify:track:7")
    _add(conn, "d1", "Unmatched", 1, None)

    rows = stats.compute_adoption(conn, {"1", "5"})
    assert rows == [("High", 2, 1), ("Low", 4, 1), ("Zero", 1, 0)]
