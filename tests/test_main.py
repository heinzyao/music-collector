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
