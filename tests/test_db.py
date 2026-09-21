"""資料庫查詢測試。"""

import sqlite3

import pytest

from music_collector.db import save_track, search_tracks


@pytest.fixture
def conn(monkeypatch, tmp_path) -> sqlite3.Connection:
    """以暫存資料庫初始化 tracks 資料表。"""
    monkeypatch.setattr("music_collector.db.DATA_DIR", tmp_path)
    monkeypatch.setattr("music_collector.db.DB_PATH", tmp_path / "tracks.db")

    from music_collector.db import init_db

    c = init_db()
    save_track(c, "Radiohead", "Kid A", "SPIN", "spotify:track:1")
    save_track(c, "Wednesday", "Elderberry Wine", "Stereogum", None)
    save_track(c, "MIKE", "Radio Static", "NME", "spotify:track:2")
    yield c
    c.close()


def test_search_matches_artist_and_title_case_insensitively(conn) -> None:
    """測試關鍵字同時比對藝人與曲名，且不分大小寫。"""
    results = search_tracks(conn, "RADIO")

    assert {(r["artist"], r["title"]) for r in results} == {
        ("Radiohead", "Kid A"),
        ("MIKE", "Radio Static"),
    }


def test_search_returns_empty_and_respects_limit(conn) -> None:
    """測試查無結果回傳空清單，且 limit 生效。"""
    assert search_tracks(conn, "zzzznotathing") == []
    assert len(search_tracks(conn, "e", limit=1)) == 1
