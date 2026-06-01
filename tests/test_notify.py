"""Notification message tests for manual import mode."""

from music_collector.notify import _build_apple_music_message


def test_build_apple_music_message_success() -> None:
    """測試成功產出手動匯入檔案時的通知文字。"""
    message = _build_apple_music_message(
        success=True,
        playlist_name="Critics' Picks — Fresh Tracks",
        track_count=15,
    )

    assert "手動匯入檔案已產出" in message
    assert "Critics' Picks — Fresh Tracks" in message
    assert "15 首" in message
    assert "匯入播放清單" in message


def test_build_apple_music_message_failure() -> None:
    """測試檔案產出失敗時的通知文字。"""
    message = _build_apple_music_message(
        success=False,
        error="寫入權限不足",
    )

    assert "Apple Music 檔案產出失敗" in message
    assert "原因：寫入權限不足" in message
    assert "請檢查執行日誌" in message
