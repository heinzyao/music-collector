"""Apple Music API guardrail tests."""

from pathlib import Path
from typing import cast
from unittest.mock import Mock

import pytest
from selenium import webdriver

from music_collector.apple_music import api


class _FakeWait:
    def __init__(self, *args: object, **kwargs: object):
        pass

    def until(self, _condition: object) -> object:
        return object()


def _make_driver() -> Mock:
    driver = Mock(spec=webdriver.Chrome)
    driver.execute_script.return_value = {
        "hasMusicKit": True,
        "devToken": "dev-token",
        "userToken": None,
    }
    return driver


def test_get_tokens_fails_fast_when_manual_login_is_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    driver = _make_driver()

    monkeypatch.setattr(api, "WebDriverWait", _FakeWait)
    monkeypatch.setattr(api.time, "sleep", lambda _seconds: None)
    monkeypatch.setattr(api, "_interactive_login_allowed", lambda: False)
    monkeypatch.setattr(
        api,
        "_click_sign_in",
        lambda _driver: pytest.fail("interactive login should not be triggered"),
    )

    with pytest.raises(api.AppleMusicAuthRequiredError, match="非互動環境"):
        api.get_tokens(cast(webdriver.Chrome, driver))


def test_import_to_apple_music_propagates_auth_required_and_closes_driver(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    csv_path = tmp_path / "tracks.csv"
    csv_path.write_text("Artist,Title\nA,T\n", encoding="utf-8")
    driver = _make_driver()

    monkeypatch.setattr(api, "create_driver", lambda: driver)
    monkeypatch.setattr(
        api,
        "get_tokens",
        lambda _driver: (_ for _ in ()).throw(
            api.AppleMusicAuthRequiredError(
                "Apple Music 需要重新登入，但目前為非互動環境"
            )
        ),
    )

    with pytest.raises(api.AppleMusicAuthRequiredError, match="非互動環境"):
        api.import_to_apple_music(str(csv_path))

    driver.quit.assert_called_once_with()
