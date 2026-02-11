"""多通道通知模組：排程執行後發送摘要。

支援通知管道：
- LINE Messaging API（既有）
- Telegram Bot API（新增）
- Slack Incoming Webhook（新增）

各通道憑證未設定時靜默跳過。
"""

import logging
from collections import Counter

import httpx

from .config import (
    LINE_CHANNEL_ID,
    LINE_CHANNEL_SECRET,
    LINE_USER_ID,
    SLACK_WEBHOOK_URL,
    TELEGRAM_BOT_TOKEN,
    TELEGRAM_CHAT_ID,
)
from .scrapers.base import Track

logger = logging.getLogger(__name__)

LINE_TOKEN_URL = "https://api.line.me/v2/oauth/accessToken"
LINE_PUSH_URL = "https://api.line.me/v2/bot/message/push"
TELEGRAM_API_URL = "https://api.telegram.org/bot{token}/sendMessage"


def send_notification(
    tracks: list[Track],
    spotify_found: list[str],
    spotify_not_found: list[Track],
    apple_music_status: str | None = None,
) -> None:
    """發送通知摘要至所有已設定的通道。

    Args:
        tracks: 本次新發現的曲目清單。
        spotify_found: 成功配對的 Spotify URI 清單。
        spotify_not_found: 在 Spotify 上未找到的曲目清單。
        apple_music_status: Apple Music 匯入狀態訊息。
    """
    message = _build_message(tracks, spotify_found, spotify_not_found, apple_music_status)

    _send_line(message)
    _send_telegram(message)
    _send_slack(message)


def send_no_new_tracks_notification() -> None:
    """發送「今日無新曲目」通知至所有已設定的通道。"""
    message = "🎵 Music Collector 執行完成\n\n今日無新曲目。"

    _send_line(message)
    _send_telegram(message)
    _send_slack(message)


# ── LINE Messaging API ──


def _get_line_access_token() -> str | None:
    """用 Channel ID + Secret 產生短期 Access Token。"""
    resp = httpx.post(
        LINE_TOKEN_URL,
        data={
            "grant_type": "client_credentials",
            "client_id": LINE_CHANNEL_ID,
            "client_secret": LINE_CHANNEL_SECRET,
        },
        timeout=15,
    )
    if resp.status_code != 200:
        logger.warning(f"LINE Token 取得失敗：{resp.status_code} {resp.text}")
        return None
    return resp.json()["access_token"]


def _send_line(message: str) -> None:
    """透過 LINE Messaging API 推送通知。"""
    if not LINE_CHANNEL_ID or not LINE_CHANNEL_SECRET or not LINE_USER_ID:
        logger.debug("LINE 憑證未設定，跳過通知。")
        return

    token = _get_line_access_token()
    if not token:
        return

    resp = httpx.post(
        LINE_PUSH_URL,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}",
        },
        json={
            "to": LINE_USER_ID,
            "messages": [{"type": "text", "text": message}],
        },
        timeout=15,
    )

    if resp.status_code == 200:
        logger.info("LINE 通知發送成功")
    else:
        logger.warning(f"LINE 通知發送失敗：{resp.status_code} {resp.text}")


# ── Telegram Bot API ──


def _send_telegram(message: str) -> None:
    """透過 Telegram Bot API 推送通知。"""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        logger.debug("Telegram 憑證未設定，跳過通知。")
        return

    url = TELEGRAM_API_URL.format(token=TELEGRAM_BOT_TOKEN)
    resp = httpx.post(
        url,
        json={
            "chat_id": TELEGRAM_CHAT_ID,
            "text": message,
            "parse_mode": "HTML",
        },
        timeout=15,
    )

    if resp.status_code == 200:
        logger.info("Telegram 通知發送成功")
    else:
        logger.warning(f"Telegram 通知發送失敗：{resp.status_code} {resp.text}")


# ── Slack Incoming Webhook ──


def _send_slack(message: str) -> None:
    """透過 Slack Incoming Webhook 推送通知。"""
    if not SLACK_WEBHOOK_URL:
        logger.debug("Slack Webhook 未設定，跳過通知。")
        return

    resp = httpx.post(
        SLACK_WEBHOOK_URL,
        json={"text": message},
        timeout=15,
    )

    if resp.status_code == 200:
        logger.info("Slack 通知發送成功")
    else:
        logger.warning(f"Slack 通知發送失敗：{resp.status_code} {resp.text}")


# ── 訊息組合 ──


def _build_message(
    tracks: list[Track],
    spotify_found: list[str],
    spotify_not_found: list[Track],
    apple_music_status: str | None = None,
) -> str:
    """組合通知文字。"""
    total = len(tracks)
    found = len(spotify_found)
    not_found = len(spotify_not_found)

    # 各來源貢獻統計
    source_counts = Counter(t.source for t in tracks)
    source_lines = "\n".join(
        f"  {source}: {count}" for source, count in source_counts.most_common()
    )

    msg = (
        f"🎵 Music Collector 執行完成\n"
        f"\n"
        f"新曲目：{total} 首\n"
        f"Spotify 配對：{found} 首\n"
        f"未找到：{not_found} 首\n"
    )

    if apple_music_status:
        msg += f"Apple Music：{apple_music_status}\n"

    msg += (
        f"\n"
        f"各來源貢獻：\n"
        f"{source_lines}"
    )
    return msg
