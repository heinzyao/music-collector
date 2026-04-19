"""Apple Music API 直接整合。

透過預存的 token 檔案直接呼叫 Apple Music REST API，
完成播放清單匯入，不依賴 Selenium 或任何瀏覽器自動化。

Token 取得流程：
    執行 ./recover-apple-music-sync.sh，在開啟的 Chrome 視窗中完成 Apple Music 登入
    （點擊右上角 Sign In → Apple ID → 2FA → 確認頭像出現），
    腳本透過 osascript 自動擷取 MusicKit token 並存至 data/apple_music_tokens.json。

每日同步流程：
    1. 讀取 data/apple_music_tokens.json（超過 23 小時視為過期）
    2. _validate_session() 驗證 token 是否可用
    3. 搜尋 CSV 曲目、刪除舊歌單、建立新歌單、分批加入曲目
"""

import csv
import json
import logging
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx

logger = logging.getLogger(__name__)

APPLE_MUSIC_BASE = "https://api.music.apple.com"
ALLOW_INTERACTIVE_LOGIN_ENV = "MUSIC_COLLECTOR_ALLOW_INTERACTIVE_APPLE_LOGIN"

# Token 檔案（由 recover-apple-music-sync.sh 透過 osascript 寫入）
TOKEN_FILE = Path("data/apple_music_tokens.json")
TOKEN_FILE_MAX_AGE_HOURS = 23

TRACKS_BATCH_SIZE = 300
SEARCH_INTERVAL = 0.15


class AppleMusicAuthRequiredError(RuntimeError):
    """Raised when Apple Music sync requires a manual login."""


def _interactive_login_allowed() -> bool:
    override = os.getenv(ALLOW_INTERACTIVE_LOGIN_ENV)
    if override is not None:
        return override.lower() in {"1", "true", "yes", "on"}
    streams = (sys.stdin, sys.stdout, sys.stderr)
    return all(getattr(stream, "isatty", lambda: False)() for stream in streams)


# ── 文字正規化與比對 ──


def _normalize(text: str) -> str:
    text = text.lower()
    text = re.sub(r"[^\w\s]", "", text)
    return re.sub(r"\s+", " ", text).strip()


def _is_match(expected: str, actual: str) -> bool:
    a, b = _normalize(expected), _normalize(actual)
    return a in b or b in a


# ── Token 載入與驗證 ──


def _load_token_file() -> tuple[str, str] | tuple[None, None]:
    """從 recover-apple-music-sync.sh 產生的 token 檔案讀取 devToken + userToken。"""
    try:
        if not TOKEN_FILE.exists():
            return None, None
        data = json.loads(TOKEN_FILE.read_text(encoding="utf-8"))
        extracted_at = data.get("extracted_at")
        if extracted_at:
            age = datetime.now(timezone.utc) - datetime.fromisoformat(extracted_at)
            if age.total_seconds() > TOKEN_FILE_MAX_AGE_HOURS * 3600:
                logger.debug(f"Token 檔案已過期（{age}），略過")
                return None, None
        dev_token = data.get("devToken")
        user_token = data.get("userToken")
        if dev_token and user_token:
            logger.info(f"從 token 檔案讀取 token（extracted_at={extracted_at}）")
            return dev_token, user_token
    except Exception as e:
        logger.debug(f"讀取 token 檔案失敗：{e}")
    return None, None


# ── Apple Music API 呼叫 ──


def _make_headers(dev_token: str, user_token: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {dev_token}",
        "Music-User-Token": user_token,
    }


def _validate_session(dev_token: str, user_token: str) -> bool:
    """Verify tokens are usable via a lightweight API call (2 attempts for transient errors)."""
    for attempt in range(2):
        try:
            resp = httpx.get(
                f"{APPLE_MUSIC_BASE}/v1/me/library/playlists",
                params={"limit": 1},
                headers=_make_headers(dev_token, user_token),
                timeout=10,
            )
            if resp.status_code == 200:
                logger.info("Session validation passed (HTTP 200)")
                return True
            logger.warning(
                f"Session validation failed: HTTP {resp.status_code} | body={resp.text[:200]}"
            )
            return False
        except Exception as e:
            if attempt == 0:
                logger.warning(
                    f"Session validation network error, retrying: {type(e).__name__}: {e}"
                )
                time.sleep(2)
            else:
                logger.warning(
                    f"Session validation network error: {type(e).__name__}: {e}"
                )
    return False


def get_storefront(dev_token: str, user_token: str) -> str:
    """取得用戶的 Apple Music storefront（地區代碼，如 'tw'）。"""
    try:
        resp = httpx.get(
            f"{APPLE_MUSIC_BASE}/v1/me/storefront",
            headers=_make_headers(dev_token, user_token),
            timeout=10,
        )
        if resp.status_code == 200:
            data = resp.json().get("data", [])
            if data:
                sf = data[0]["id"]
                logger.info(f"Storefront：{sf}")
                return sf
        logger.warning(
            f"無法取得 storefront：HTTP {resp.status_code} | body={resp.text[:200]}，使用預設 us"
        )
    except Exception as e:
        logger.warning(f"無法取得 storefront：{e}，使用預設 us")
    return "us"


def search_track(
    artist: str,
    title: str,
    storefront: str,
    dev_token: str,
    user_token: str,
) -> str | None:
    """在 Apple Music catalog 搜尋曲目，回傳 track ID 或 None。

    策略：
    1. 精確查詢 "{title} {artist}"
    2. 反向查詢 "{artist} {title}"
    兩種查詢都做藝人 + 曲名雙重驗證。
    """
    headers = _make_headers(dev_token, user_token)
    url = f"{APPLE_MUSIC_BASE}/v1/catalog/{storefront}/search"

    for term in [f"{title} {artist}", f"{artist} {title}"]:
        try:
            resp = httpx.get(
                url,
                params={"term": term, "types": "songs", "limit": 10},
                headers=headers,
                timeout=15,
            )
            if resp.status_code != 200:
                logger.debug(f"搜尋失敗 HTTP {resp.status_code}：{term}")
                continue

            songs = resp.json().get("results", {}).get("songs", {}).get("data", [])
            for song in songs:
                attrs = song.get("attributes", {})
                result_title = attrs.get("name", "")
                result_artist = attrs.get("artistName", "")
                if _is_match(title, result_title) and _is_match(artist, result_artist):
                    return song["id"]
        except Exception as e:
            logger.debug(f"搜尋例外（{term}）：{e}")

    return None


def _get_existing_playlist_id(name: str, dev_token: str, user_token: str) -> str | None:
    """從用戶 library 找出同名播放清單的 ID（取最新一個）。"""
    headers = _make_headers(dev_token, user_token)
    all_playlists = []
    offset = 0
    limit = 100
    while True:
        try:
            resp = httpx.get(
                f"{APPLE_MUSIC_BASE}/v1/me/library/playlists",
                params={"limit": limit, "offset": offset},
                headers=headers,
                timeout=15,
            )
            if resp.status_code != 200:
                break
            data = resp.json().get("data", [])
            all_playlists.extend(data)
            if len(data) < limit:
                break
            offset += limit
        except Exception as e:
            logger.warning(f"取得播放清單列表失敗：{e}")
            break

    matches = [p for p in all_playlists if p.get("attributes", {}).get("name") == name]
    if not matches:
        return None
    matches.sort(
        key=lambda p: p.get("attributes", {}).get("dateAdded", ""),
        reverse=True,
    )
    return matches[0]["id"]


def _delete_playlist_by_id(playlist_id: str, dev_token: str, user_token: str) -> bool:
    """透過 API 刪除指定 ID 的播放清單。"""
    try:
        resp = httpx.delete(
            f"{APPLE_MUSIC_BASE}/v1/me/library/playlists/{playlist_id}",
            headers=_make_headers(dev_token, user_token),
            timeout=15,
        )
        return resp.status_code in (200, 204)
    except Exception as e:
        logger.warning(f"刪除播放清單失敗：{e}")
        return False


def create_playlist(name: str, dev_token: str, user_token: str) -> str | None:
    """建立新播放清單，回傳 playlist ID 或 None。"""
    try:
        resp = httpx.post(
            f"{APPLE_MUSIC_BASE}/v1/me/library/playlists",
            json={"attributes": {"name": name}},
            headers={
                **_make_headers(dev_token, user_token),
                "Content-Type": "application/json",
            },
            timeout=15,
        )
        if resp.status_code in (200, 201):
            data = resp.json().get("data", [])
            if data:
                pid = data[0]["id"]
                logger.info(f"已建立播放清單「{name}」（ID: {pid}）")
                return pid
        logger.error(f"建立播放清單失敗：HTTP {resp.status_code} {resp.text[:200]}")
    except Exception as e:
        logger.error(f"建立播放清單例外：{e}")
    return None


def add_tracks_to_playlist(
    playlist_id: str,
    track_ids: list[str],
    dev_token: str,
    user_token: str,
) -> int:
    """分批將 catalog track 加入播放清單，回傳成功加入數量。"""
    headers = {
        **_make_headers(dev_token, user_token),
        "Content-Type": "application/json",
    }
    added = 0
    total = len(track_ids)

    for i in range(0, total, TRACKS_BATCH_SIZE):
        batch = track_ids[i : i + TRACKS_BATCH_SIZE]
        try:
            resp = httpx.post(
                f"{APPLE_MUSIC_BASE}/v1/me/library/playlists/{playlist_id}/tracks",
                json={"data": [{"id": tid, "type": "songs"} for tid in batch]},
                headers=headers,
                timeout=30,
            )
            if resp.status_code in (200, 201, 204):
                added += len(batch)
                logger.info(
                    f"已加入第 {i + 1}–{i + len(batch)} 首"
                    f"（共 {total} 首，累計 {added} 首）"
                )
            else:
                logger.error(
                    f"加入曲目失敗（批次 {i // TRACKS_BATCH_SIZE + 1}）："
                    f"HTTP {resp.status_code} {resp.text[:100]}"
                )
        except Exception as e:
            logger.error(f"加入曲目例外（批次 {i // TRACKS_BATCH_SIZE + 1}）：{e}")

    return added


def _import_with_tokens(
    dev_token: str,
    user_token: str,
    tracks: list[tuple[str, str]],
    name: str,
) -> bool:
    """搜尋曲目、建立播放清單、加入曲目（純 REST API，不依賴瀏覽器）。"""
    storefront = get_storefront(dev_token, user_token)

    print(f"\n  正在搜尋 {len(tracks)} 首曲目...")
    found_ids: list[str] = []
    not_found: list[tuple[str, str]] = []

    for i, (artist, title) in enumerate(tracks):
        track_id = search_track(artist, title, storefront, dev_token, user_token)
        if track_id:
            found_ids.append(track_id)
        else:
            not_found.append((artist, title))

        if (i + 1) % 50 == 0:
            logger.info(
                f"搜尋進度：{i + 1}/{len(tracks)}"
                f"（找到 {len(found_ids)}，未找到 {len(not_found)}）"
            )
        time.sleep(SEARCH_INTERVAL)

    logger.info(f"搜尋完成：{len(found_ids)}/{len(tracks)} 首找到")
    if not_found:
        logger.warning(f"以下 {len(not_found)} 首未找到：")
        for artist, title in not_found[:20]:
            logger.warning(f"  {artist} — {title}")
        if len(not_found) > 20:
            logger.warning(f"  ...及其他 {len(not_found) - 20} 首")

    if not found_ids:
        logger.error("未找到任何曲目，中止匯入")
        return False

    old_id = _get_existing_playlist_id(name, dev_token, user_token)
    if old_id:
        if _delete_playlist_by_id(old_id, dev_token, user_token):
            logger.info(f"已刪除舊播放清單「{name}」（ID: {old_id}）")
        else:
            logger.warning("舊播放清單刪除失敗，繼續建立新版本")
        time.sleep(2)

    playlist_id = create_playlist(name, dev_token, user_token)
    if not playlist_id:
        return False

    added = add_tracks_to_playlist(playlist_id, found_ids, dev_token, user_token)

    print(
        f"\n  匯入完成！{added}/{len(tracks)} 首已加入"
        f"（{len(not_found)} 首未在 Apple Music 找到）"
    )
    print("  請至 Apple Music 確認播放清單。\n")
    return added > 0


# ── 主入口 ──


def import_to_apple_music(
    csv_path: str,
    keep_browser_open: bool = False,
    playlist_name: str | None = None,
) -> bool:
    """將 CSV 檔案透過 Apple Music API 直接匯入播放清單。

    Token 來源：data/apple_music_tokens.json（由 recover-apple-music-sync.sh 寫入）。
    若 token 不存在或已過期，拋出 AppleMusicAuthRequiredError。

    Args:
        csv_path: CSV 檔案路徑（欄位：Artist, Title）
        keep_browser_open: 已廢棄，僅保留相容性
        playlist_name: 目標播放清單名稱（若不指定則使用 CSV 檔名）
    """
    csv_path = str(Path(csv_path).resolve())
    if not Path(csv_path).exists():
        logger.error(f"CSV 檔案不存在：{csv_path}")
        return False

    tracks: list[tuple[str, str]] = []
    with open(csv_path, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            artist = (row.get("Artist") or row.get("artist") or "").strip()
            title = (row.get("Title") or row.get("title") or "").strip()
            if artist and title:
                tracks.append((artist, title))

    if not tracks:
        logger.error("CSV 無有效曲目")
        return False

    name = playlist_name or Path(csv_path).stem
    logger.info(f"準備匯入 {len(tracks)} 首曲目至「{name}」")

    dev_token, user_token = _load_token_file()
    if not dev_token or not user_token:
        raise AppleMusicAuthRequiredError(
            "Apple Music token 不存在或已過期。"
            " 請在終端執行 ./recover-apple-music-sync.sh 重新取得 token。"
        )

    if not _validate_session(dev_token, user_token):
        raise AppleMusicAuthRequiredError(
            "Apple Music token 驗證失敗（已過期或被撤銷）。"
            " 請在終端執行 ./recover-apple-music-sync.sh 重新取得 token。"
        )

    logger.info("Token 驗證通過，開始匯入...")
    return _import_with_tokens(dev_token, user_token, tracks, name)
