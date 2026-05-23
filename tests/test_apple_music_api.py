"""Apple Music API guardrail tests."""

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx
import pytest
import respx

from music_collector.apple_music import api


# ── _load_token_file ──


def test_load_token_file_returns_tokens_when_fresh(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    token_file = tmp_path / "apple_music_tokens.json"
    extracted_at = datetime.now(timezone.utc).isoformat()
    token_file.write_text(
        json.dumps({"devToken": "dev", "userToken": "user", "extracted_at": extracted_at}),
        encoding="utf-8",
    )
    monkeypatch.setattr(api, "TOKEN_FILE", token_file)

    dev, user = api._load_token_file()
    assert dev == "dev"
    assert user == "user"


def test_load_token_file_rejects_expired_token(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    token_file = tmp_path / "apple_music_tokens.json"
    old_time = (datetime.now(timezone.utc) - timedelta(hours=169)).isoformat()
    token_file.write_text(
        json.dumps({"devToken": "dev", "userToken": "user", "extracted_at": old_time}),
        encoding="utf-8",
    )
    monkeypatch.setattr(api, "TOKEN_FILE", token_file)

    dev, user = api._load_token_file()
    assert dev is None
    assert user is None


def test_load_token_file_returns_none_when_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(api, "TOKEN_FILE", tmp_path / "nonexistent.json")

    dev, user = api._load_token_file()
    assert dev is None
    assert user is None


# ── _validate_session ──


@respx.mock
def test_validate_session_returns_true_on_200() -> None:
    respx.get("https://api.music.apple.com/v1/me/library/playlists").mock(
        return_value=httpx.Response(200, json={"data": []})
    )
    assert api._validate_session("dev", "user") is True


@respx.mock
def test_validate_session_returns_false_on_401() -> None:
    respx.get("https://api.music.apple.com/v1/me/library/playlists").mock(
        return_value=httpx.Response(401, text="Unauthorized")
    )
    assert api._validate_session("dev", "user") is False


@respx.mock
def test_validate_session_retries_on_network_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(api.time, "sleep", lambda _: None)
    call_count = 0

    def side_effect(request):
        nonlocal call_count
        call_count += 1
        if call_count < 2:
            raise httpx.ConnectError("timeout")
        return httpx.Response(200, json={"data": []})

    respx.get("https://api.music.apple.com/v1/me/library/playlists").mock(
        side_effect=side_effect
    )
    assert api._validate_session("dev", "user") is True
    assert call_count == 2


# ── import_to_apple_music ──


def test_import_raises_auth_error_when_token_file_missing(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    csv_path = tmp_path / "tracks.csv"
    csv_path.write_text("Artist,Title\nRadiohead,Creep\n", encoding="utf-8")
    monkeypatch.setattr(api, "_load_token_file", lambda: (None, None))

    with pytest.raises(api.AppleMusicAuthRequiredError, match="token 不存在"):
        api.import_to_apple_music(str(csv_path))


def test_import_raises_auth_error_when_session_invalid(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    csv_path = tmp_path / "tracks.csv"
    csv_path.write_text("Artist,Title\nRadiohead,Creep\n", encoding="utf-8")
    monkeypatch.setattr(api, "_load_token_file", lambda: ("dev", "user"))
    monkeypatch.setattr(api, "_validate_session", lambda _d, _u: False)

    with pytest.raises(api.AppleMusicAuthRequiredError, match="驗證失敗"):
        api.import_to_apple_music(str(csv_path))


def test_import_calls_import_with_tokens_when_session_valid(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    csv_path = tmp_path / "tracks.csv"
    csv_path.write_text("Artist,Title\nRadiohead,Creep\n", encoding="utf-8")
    monkeypatch.setattr(api, "_load_token_file", lambda: ("dev", "user"))
    monkeypatch.setattr(api, "_validate_session", lambda _d, _u: True)

    called_with: list = []

    def fake_import(dev_token, user_token, tracks, name):
        called_with.extend([dev_token, user_token, tracks, name])
        return True

    monkeypatch.setattr(api, "_import_with_tokens", fake_import)

    result = api.import_to_apple_music(str(csv_path), playlist_name="Test")
    assert result is True
    assert called_with[0] == "dev"
    assert called_with[1] == "user"
    assert called_with[2] == [("Radiohead", "Creep")]
    assert called_with[3] == "Test"


def test_import_returns_false_for_empty_csv(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    csv_path = tmp_path / "empty.csv"
    csv_path.write_text("Artist,Title\n", encoding="utf-8")
    monkeypatch.setattr(api, "_load_token_file", lambda: ("dev", "user"))
    monkeypatch.setattr(api, "_validate_session", lambda _d, _u: True)

    result = api.import_to_apple_music(str(csv_path))
    assert result is False


# ── _fetch_all_library_playlists / list_playlists_by_prefix ──


@respx.mock
def test_fetch_all_library_playlists_paginates() -> None:
    """分頁：第一批滿 100 筆，第二批 3 筆，應共回傳 103 筆。"""
    page1 = {"data": [{"id": f"p{i}", "attributes": {"name": "A"}} for i in range(100)]}
    page2 = {"data": [{"id": f"q{i}", "attributes": {"name": "B"}} for i in range(3)]}
    call_count = 0

    def paginate(request):
        nonlocal call_count
        call_count += 1
        return httpx.Response(200, json=page1 if call_count == 1 else page2)

    respx.get("https://api.music.apple.com/v1/me/library/playlists").mock(
        side_effect=paginate
    )
    result = api._fetch_all_library_playlists("dev", "user")
    assert len(result) == 103
    assert call_count == 2


@respx.mock
def test_list_playlists_by_prefix_filters_correctly() -> None:
    playlists = [
        {"id": "p1", "attributes": {"name": "Critics' Picks — Fresh Tracks"}},
        {"id": "p2", "attributes": {"name": "Critics' Picks — 2026 Q1"}},
        {"id": "p3", "attributes": {"name": "Other Playlist"}},
        {"id": "p4", "attributes": {"name": "Critics' Picks — Fresh Tracks"}},
    ]
    respx.get("https://api.music.apple.com/v1/me/library/playlists").mock(
        return_value=httpx.Response(200, json={"data": playlists})
    )
    result = api.list_playlists_by_prefix("Critics' Picks", "dev", "user")
    assert len(result) == 3
    assert all(r["name"].startswith("Critics' Picks") for r in result)
    assert not any(r["name"] == "Other Playlist" for r in result)


# ── _get_all_playlist_ids_by_name ──


@respx.mock
def test_get_all_playlist_ids_by_name_returns_all_matches() -> None:
    playlists = [
        {"id": "old1", "attributes": {"name": "My Playlist", "dateAdded": "2026-01-01"}},
        {"id": "old2", "attributes": {"name": "My Playlist", "dateAdded": "2026-02-01"}},
        {"id": "other", "attributes": {"name": "Other"}},
    ]
    respx.get("https://api.music.apple.com/v1/me/library/playlists").mock(
        return_value=httpx.Response(200, json={"data": playlists})
    )
    ids = api._get_all_playlist_ids_by_name("My Playlist", "dev", "user")
    assert set(ids) == {"old1", "old2"}


@respx.mock
def test_get_all_playlist_ids_by_name_returns_empty_when_none() -> None:
    respx.get("https://api.music.apple.com/v1/me/library/playlists").mock(
        return_value=httpx.Response(200, json={"data": []})
    )
    ids = api._get_all_playlist_ids_by_name("Missing", "dev", "user")
    assert ids == []


# ── AppleScript fallback helpers ──


def test_delete_playlists_by_name_applescript_skips_non_macos(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(api.sys, "platform", "linux")
    result = api._delete_playlists_by_name_applescript("Critics' Picks — Fresh Tracks")
    assert result is False


def test_delete_playlists_by_prefix_applescript_skips_non_macos(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(api.sys, "platform", "linux")
    result = api._delete_playlists_by_prefix_applescript("Critics' Picks")
    assert result == 0


def test_delete_playlists_by_prefix_applescript_returns_count_on_macos(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(api.sys, "platform", "darwin")
    fake_result = type("R", (), {"returncode": 0, "stdout": "3\n"})()
    monkeypatch.setattr(api.subprocess, "run", lambda *a, **kw: fake_result)

    count = api._delete_playlists_by_prefix_applescript("Critics' Picks")
    assert count == 3
