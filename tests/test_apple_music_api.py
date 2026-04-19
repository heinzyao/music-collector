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
    old_time = (datetime.now(timezone.utc) - timedelta(hours=25)).isoformat()
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
