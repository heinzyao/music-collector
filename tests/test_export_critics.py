"""critics.json 匯出測試（mock GCS，不打網路）。"""

import json
import sys
import types
from unittest.mock import MagicMock

from music_collector import db, export


def _db(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "tracks.db")
    conn = db.init_db()
    rows = [
        ("Old", "Too Old", "A", "spotify:track:old", "-91 days"),
        ("NoUri", "Null", "A", None, "-1 days"),
        ("Empty", "Blank", "A", "", "-1 days"),
        ("Mid", "Mid", "B", "spotify:track:mid", "-10 days"),
        ("New", "New", "C", "spotify:track:new", "-1 hours"),
        ("Edge", "Edge", "B", "spotify:track:edge", "-89 days"),
    ]
    for artist, title, source, uri, offset in rows:
        conn.execute(
            "INSERT INTO tracks (artist, title, source, spotify_uri, added_at) "
            "VALUES (?, ?, ?, ?, datetime('now', ?))",
            (artist, title, source, uri, offset),
        )
    conn.commit()
    return conn


def test_build_critics_filters_and_sorts(tmp_path, monkeypatch):
    conn = _db(tmp_path, monkeypatch)
    payload = export.build_critics(conn)
    assert [t["artist"] for t in payload["tracks"]] == ["New", "Mid", "Edge"]
    t = payload["tracks"][0]
    assert set(t) == {"artist", "title", "source", "spotify_uri", "added_at"}
    assert t["added_at"].endswith("Z") and "T" in t["added_at"]
    assert payload["generated_at"].endswith("+00:00")


def test_build_critics_dedupes_uri(tmp_path, monkeypatch):
    conn = _db(tmp_path, monkeypatch)
    conn.execute(
        "INSERT INTO tracks (artist, title, source, spotify_uri, added_at) "
        "VALUES ('Review: Mid''s', 'Mid', 'Slant', 'spotify:track:mid', datetime('now', '-5 days'))"
    )
    tracks = export.build_critics(conn)["tracks"]
    assert [t["artist"] for t in tracks] == ["New", "Review: Mid's", "Edge"]


def test_build_critics_caps_at_limit(tmp_path, monkeypatch):
    conn = _db(tmp_path, monkeypatch)
    monkeypatch.setattr(export, "CRITICS_LIMIT", 2)
    assert [t["artist"] for t in export.build_critics(conn)["tracks"]] == ["New", "Mid"]


def test_build_critics_default_limit_300(tmp_path, monkeypatch):
    conn = _db(tmp_path, monkeypatch)
    conn.executemany(
        "INSERT INTO tracks (artist, title, source, spotify_uri) VALUES (?, ?, ?, ?)",
        [(f"a{i}", f"t{i}", f"S{i % 10}", f"spotify:track:{i}") for i in range(500)],
    )
    assert len(export.build_critics(conn)["tracks"]) == 300


def test_build_critics_caps_per_source(tmp_path, monkeypatch):
    conn = _db(tmp_path, monkeypatch)
    monkeypatch.setattr(export, "CRITICS_PER_SOURCE", 1)
    # B 有 Mid、Edge 兩筆，只留較新的 Mid
    assert [t["artist"] for t in export.build_critics(conn)["tracks"]] == ["New", "Mid"]


def test_build_critics_default_per_source_40(tmp_path, monkeypatch):
    conn = _db(tmp_path, monkeypatch)
    conn.executemany(
        "INSERT INTO tracks (artist, title, source, spotify_uri) VALUES (?, ?, 'X', ?)",
        [(f"a{i}", f"t{i}", f"spotify:track:{i}") for i in range(50)],
    )
    sources = [t["source"] for t in export.build_critics(conn)["tracks"]]
    assert sources.count("X") == 40


def _fake_storage(monkeypatch, upload_side_effect=None):
    client = MagicMock()
    blob = client.return_value.bucket.return_value.blob.return_value
    blob.upload_from_string.side_effect = upload_side_effect
    storage = types.SimpleNamespace(Client=client)
    cloud = types.ModuleType("google.cloud")
    cloud.storage = storage
    monkeypatch.setitem(sys.modules, "google.cloud", cloud)
    monkeypatch.setitem(sys.modules, "google.cloud.storage", storage)
    return client, blob


def test_export_critics_skips_without_env(tmp_path, monkeypatch):
    _db(tmp_path, monkeypatch)
    monkeypatch.setattr(export, "CRITICS_GCS_URI", "")
    client, _ = _fake_storage(monkeypatch)
    export.export_critics()
    client.assert_not_called()


def test_export_critics_uploads(tmp_path, monkeypatch):
    _db(tmp_path, monkeypatch)
    monkeypatch.setattr(export, "CRITICS_GCS_URI", "gs://bkt/dir/critics.json")
    client, blob = _fake_storage(monkeypatch)
    export.export_critics()
    client.return_value.bucket.assert_called_once_with("bkt")
    client.return_value.bucket.return_value.blob.assert_called_once_with("dir/critics.json")
    data = json.loads(blob.upload_from_string.call_args.args[0])
    assert len(data["tracks"]) == 3


def test_export_critics_upload_failure_does_not_raise(tmp_path, monkeypatch, caplog):
    _db(tmp_path, monkeypatch)
    monkeypatch.setattr(export, "CRITICS_GCS_URI", "gs://bkt/critics.json")
    _fake_storage(monkeypatch, upload_side_effect=RuntimeError("403"))
    export.export_critics()
    assert "critics.json 匯出失敗" in caplog.text


def test_export_critics_out_writes_file_without_upload(tmp_path, monkeypatch):
    _db(tmp_path, monkeypatch)
    monkeypatch.setattr(export, "CRITICS_GCS_URI", "gs://bkt/critics.json")
    client, _ = _fake_storage(monkeypatch)
    out = tmp_path / "critics.json"
    export.export_critics(out)
    assert len(json.loads(out.read_text())["tracks"]) == 3
    client.assert_not_called()
