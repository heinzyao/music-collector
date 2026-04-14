"""Notification message tests."""

from music_collector.notify import _build_apple_music_message


def test_build_apple_music_message_marks_auth_required_as_skipped() -> None:
    message = _build_apple_music_message(
        success=False,
        playlist_name="Critics' Picks — Fresh Tracks",
        error="Apple Music 需要重新登入，但目前為非互動環境，已略過同步。",
    )

    assert "Apple Music 已略過" in message
    assert "需要重新登入" in message
    assert "./bootstrap-apple-music-login.sh" in message
    assert "./sync-apple-music.sh" in message
    assert "Critics' Picks — Fresh Tracks" in message


def test_build_apple_music_message_keeps_general_failure_copy() -> None:
    message = _build_apple_music_message(
        success=False,
        error="HTTP 500",
    )

    assert "Apple Music 匯入失敗" in message
    assert "原因：HTTP 500" in message
    assert "請檢查日誌或手動匯入" in message
