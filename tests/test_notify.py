"""通知訊息組合測試。"""

from music_collector.notify import _build_message, send_error_notification
from music_collector.scrapers.base import Track


def _track(source: str) -> Track:
    return Track(artist="De La Rose", title="La Monda", source=source)


def test_build_message_summarises_sources() -> None:
    """測試執行摘要包含統計數字與各來源貢獻。"""
    message = _build_message(
        [_track("Pitchfork"), _track("Stereogum")],
        ["spotify:track:abc"],
        [_track("NME")],
    )

    assert "新曲目：2 首" in message
    assert "Spotify 配對：1 首" in message
    assert "未找到：1 首" in message
    assert "Pitchfork: 1" in message


def test_send_error_notification_includes_reason_and_action(monkeypatch) -> None:
    """測試失敗警示同時送出原因與修復動作。"""
    sent: list[str] = []
    for channel in ("_send_line", "_send_telegram", "_send_slack"):
        monkeypatch.setattr(
            "music_collector.notify." + channel, lambda msg: sent.append(msg)
        )

    send_error_notification("Spotify 連線失敗", "invalid_grant", "請重新授權。")

    assert len(sent) == 3
    assert "Spotify 連線失敗" in sent[0]
    assert "原因：invalid_grant" in sent[0]
    assert "請重新授權。" in sent[0]
