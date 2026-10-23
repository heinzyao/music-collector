"""main 主流程測試。"""

import sqlite3

from music_collector import db, main
from music_collector.scrapers.base import Track


class _FakeScraper:
    name = "Fake"

    def fetch_tracks(self):
        return [Track(artist="Artist", title="Title", source="Fake")]


def _count_checks(path) -> int:
    with sqlite3.connect(path) as conn:
        return conn.execute("SELECT COUNT(*) FROM source_checks").fetchone()[0]


def test_dry_run_does_not_write_source_checks(tmp_path, monkeypatch):
    db_path = tmp_path / "tracks.db"
    monkeypatch.setattr(db, "DB_PATH", db_path)
    monkeypatch.setattr(main, "ALL_SCRAPERS", [_FakeScraper()])

    main.run(dry_run=True)
    assert _count_checks(db_path) == 0

    # 對照組：預設仍會寫入，確保上面的斷言不是空轉
    main.collect_tracks()
    assert _count_checks(db_path) == 1


def test_rate_limited_write_skips_db_and_notifies(tmp_path, monkeypatch):
    """寫歌單被 429 擋下時不能存 DB，否則這批歌下次不算新曲目、永遠進不了主歌單。"""
    db_path = tmp_path / "tracks.db"
    monkeypatch.setattr(db, "DB_PATH", db_path)
    monkeypatch.setattr(main, "collect_tracks", lambda **kw: [Track("Artist", "Title", "Fake")])
    monkeypatch.setattr(main, "get_spotify_client", lambda: None)
    monkeypatch.setattr(main, "get_or_create_playlist", lambda sp: "pl")
    monkeypatch.setattr(main, "search_track", lambda sp, a, t: "spotify:track:x")

    def limited(*a):
        raise main.RateLimited(3600)

    monkeypatch.setattr(main, "add_tracks_to_playlist", limited)
    notes = []
    monkeypatch.setattr(main, "send_error_notification", lambda *a: notes.append(a))

    main.run()
    assert notes and notes[0][0] == "Spotify 限流" and "1.0 小時" in notes[0][1]
    db.init_db().close()
    with sqlite3.connect(db_path) as conn:
        assert conn.execute("SELECT COUNT(*) FROM tracks").fetchone()[0] == 0
