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


def test_focus_login_window_activates_chrome_on_macos(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    driver = _make_driver()
    run_mock = Mock()

    monkeypatch.setattr(api.sys, "platform", "darwin")
    monkeypatch.setattr(api.subprocess, "run", run_mock)

    api._focus_login_window(cast(webdriver.Chrome, driver))

    driver.execute_script.assert_called_once()
    run_mock.assert_called_once()


def test_focus_login_window_skips_osascript_off_macos(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    driver = _make_driver()
    run_mock = Mock()

    monkeypatch.setattr(api.sys, "platform", "linux")
    monkeypatch.setattr(api.subprocess, "run", run_mock)

    api._focus_login_window(cast(webdriver.Chrome, driver))

    driver.execute_script.assert_called_once()
    run_mock.assert_not_called()


def test_wait_for_user_token_skips_token_polling_during_inline_grace_period(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    driver = _make_driver()
    driver.current_window_handle = "main"
    driver.window_handles = ["main"]

    class _StopLoop(Exception):
        pass

    def execute_script(script: str):
        if script == api._EXTRACT_TOKENS_JS:
            pytest.fail(
                "token polling should be paused during inline input grace period"
            )
        return None

    driver.execute_script.side_effect = execute_script
    monkeypatch.setattr(api.time, "time", lambda: 0.0)
    monkeypatch.setattr(api, "_focus_login_window", lambda _driver: None)

    def stop_sleep(_seconds: float) -> None:
        raise _StopLoop

    monkeypatch.setattr(api.time, "sleep", stop_sleep)

    with pytest.raises(_StopLoop):
        api._wait_for_user_token(cast(webdriver.Chrome, driver), timeout=30)


def test_wait_for_user_token_resumes_polling_after_inline_grace_period(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    driver = _make_driver()
    driver.current_window_handle = "main"
    driver.window_handles = ["main"]

    times = iter([0.0, 0.0, 91.0, 91.0])

    def fake_time() -> float:
        return next(times)

    def execute_script(script: str):
        if script == api._EXTRACT_TOKENS_JS:
            return {"userToken": "user-token"}
        return None

    driver.execute_script.side_effect = execute_script
    monkeypatch.setattr(api.time, "time", fake_time)
    monkeypatch.setattr(api.time, "sleep", lambda _seconds: None)
    monkeypatch.setattr(api, "_focus_login_window", lambda _driver: None)

    user_token = api._wait_for_user_token(cast(webdriver.Chrome, driver), timeout=300)

    assert user_token == "user-token"
