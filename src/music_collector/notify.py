"""LINE Messaging API 通知模組：排程執行後發送摘要。

使用 httpx 直接呼叫 LINE push message API，無需安裝 line-bot-sdk。
每次發送前以 Channel ID + Secret 自動產生短期 Access Token，免除過期問題。
憑證未設定時靜默跳過。
"""

import logging
from collections import Counter

import httpx

from .config import LINE_CHANNEL_ID, LINE_CHANNEL_SECRET, LINE_USER_ID
from .scrapers.base import Track

logger = logging.getLogger(__name__)

LINE_TOKEN_URL = "https://api.line.me/v2/oauth/accessToken"
LINE_PUSH_URL = "https://api.line.me/v2/bot/message/push"


def _get_access_token() -> str | None:
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


def send_notification(
    tracks: list[Track],
    spotify_found: list[str],
    spotify_not_found: list[Track],
) -> None:
    """發送 LINE 通知摘要。

    Args:
        tracks: 本次新發現的曲目清單。
        spotify_found: 成功配對的 Spotify URI 清單。
        spotify_not_found: 在 Spotify 上未找到的曲目清單。
    """
    if not LINE_CHANNEL_ID or not LINE_CHANNEL_SECRET or not LINE_USER_ID:
        logger.debug("LINE 憑證未設定，跳過通知。")
        return

    token = _get_access_token()
    if not token:
        return

    message = _build_message(tracks, spotify_found, spotify_not_found)

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


def _build_message(
    tracks: list[Track],
    spotify_found: list[str],
    spotify_not_found: list[Track],
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

    return (
        f"🎵 Music Collector 執行完成\n"
        f"\n"
        f"新曲目：{total} 首\n"
        f"Spotify 配對：{found} 首\n"
        f"未找到：{not_found} 首\n"
        f"\n"
        f"各來源貢獻：\n"
        f"{source_lines}"
    )
