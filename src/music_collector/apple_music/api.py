"""Apple Music API 直接整合。

透過 music.apple.com 提取 MusicKit token，直接呼叫 Apple Music REST API
完成播放清單匯入，不依賴任何第三方轉換服務。

流程：
    1. Selenium 開啟 music.apple.com，提取 developer token + user token
    2. 逐一搜尋 CSV 中的 (artist, title)，取得 Apple Music catalog track ID
    3. 刪除同名舊歌單，建立新歌單，分批加入曲目
"""

import csv
import logging
import os
import re
import sys
import time
from pathlib import Path

import httpx
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from selenium.common.exceptions import TimeoutException

from .browser import create_driver, save_debug_screenshot

logger = logging.getLogger(__name__)

APPLE_MUSIC_BASE = "https://api.music.apple.com"
MUSIC_APPLE_URL = "https://music.apple.com"
ALLOW_INTERACTIVE_LOGIN_ENV = "MUSIC_COLLECTOR_ALLOW_INTERACTIVE_APPLE_LOGIN"

# 每批加入曲目數（Apple Music API 單次上限）
TRACKS_BATCH_SIZE = 300

# 搜尋各請求間隔（避免觸發 rate limit）
SEARCH_INTERVAL = 0.15


class AppleMusicAuthRequiredError(RuntimeError):
    """Raised when Apple Music sync requires a manual login."""


def _interactive_login_allowed() -> bool:
    """Return whether this process can safely prompt for Apple ID login.

    Scheduled runs redirect stdio to log files, so waiting for an interactive
    sign-in modal only burns time and fails later. Allow an explicit env override
    for manual debugging in non-standard terminals.
    """
    override = os.getenv(ALLOW_INTERACTIVE_LOGIN_ENV)
    if override is not None:
        return override.lower() in {"1", "true", "yes", "on"}

    streams = (sys.stdin, sys.stdout, sys.stderr)
    return all(getattr(stream, "isatty", lambda: False)() for stream in streams)


# ── 文字正規化與比對 ──


def _normalize(text: str) -> str:
    """小寫、移除標點，用於藝人/曲名比對。"""
    text = text.lower()
    text = re.sub(r"[^\w\s]", "", text)
    return re.sub(r"\s+", " ", text).strip()


def _is_match(expected: str, actual: str) -> bool:
    """子字串包含即視為吻合（與 Spotify 搜尋邏輯一致）。"""
    a, b = _normalize(expected), _normalize(actual)
    return a in b or b in a


# ── Token 取得 ──

# music.apple.com 上取 token 用的 JS：
# 直接讀取 MusicKit 實例的公開屬性，不依賴 TuneMyMusic 的 localStorage key。
_EXTRACT_TOKENS_JS = """
var music = null;
if (typeof MusicKit !== 'undefined') {
    try { music = MusicKit.getInstance(); } catch(e) {}
}
if (!music && window.music) music = window.music;

var devToken = null;
var userToken = null;

if (music) {
    devToken = music.developerToken || null;
    userToken = music.musicUserToken || null;
}

// music.apple.com 有時將 user token 存在 media-user-token cookie
if (!userToken) {
    try {
        var match = document.cookie.match(/media-user-token=([^;]+)/);
        if (match) userToken = decodeURIComponent(match[1]);
    } catch(e) {}
}

// 從 localStorage 的 music.{appId}.u 格式取得（備援）
if (!userToken) {
    try {
        for (var i = 0; i < localStorage.length; i++) {
            var key = localStorage.key(i);
            if (/^music\\..+\\.u$/.test(key)) {
                userToken = localStorage.getItem(key);
                break;
            }
        }
    } catch(e) {}
}

return {
    devToken: devToken,
    userToken: userToken,
    isAuthorized: !!(music && music.isAuthorized),
    hasMusicKit: typeof MusicKit !== 'undefined'
};
"""


def _click_sign_in(driver: webdriver.Chrome) -> None:
    """點擊 music.apple.com 的 Sign In 按鈕，觸發 Apple ID 登入流程。

    使用 JS click 繞過可能存在的 overlay 攔截問題。
    若未找到按鈕則降級至 MusicKit.authorize()。
    """
    # JS click 可繞過 overlay 阻擋，直接觸發 click 事件
    clicked = driver.execute_script(
        """
        // music.apple.com 使用 Svelte，Sign In 按鈕的 class 含 'signin'
        var btns = document.querySelectorAll(
            'button.signin, button[class*="signin"]'
        );
        for (var i = 0; i < btns.length; i++) {
            var b = btns[i];
            // 取可見的那個（offsetParent !== null 或有尺寸）
            if (b.offsetParent !== null || b.offsetWidth > 0 || b.offsetHeight > 0) {
                b.click();
                return 'button';
            }
        }
        // 降級：MusicKit.authorize()
        try {
            MusicKit.getInstance().authorize().catch(function(){});
            return 'authorize';
        } catch(e) {}
        return 'failed';
        """
    )
    if clicked == "button":
        logger.info("已 JS 點擊 Sign In 按鈕")
    elif clicked == "authorize":
        logger.info("已呼叫 MusicKit.authorize()")
    else:
        logger.warning("Sign In 觸發失敗（未找到按鈕，authorize() 也拋出例外）")


def _wait_for_user_token(driver: webdriver.Chrome, timeout: int = 300) -> str | None:
    """等待 Apple ID 登入完成並回傳 user token。

    1. 偵測登入彈窗（新視窗）並切換過去讓用戶清楚看到
    2. 等待彈窗關閉（用戶完成登入）
    3. 切回主視窗後提取 user token
    """
    main_window = driver.current_window_handle
    start = time.time()

    # ── 等待登入彈窗出現（最多 30 秒） ──
    popup_handle = None
    for _ in range(15):
        handles = driver.window_handles
        new_handles = [h for h in handles if h != main_window]
        if new_handles:
            popup_handle = new_handles[0]
            break
        time.sleep(2)

    if popup_handle:
        # 切至彈窗，讓用戶看到登入畫面
        try:
            driver.switch_to.window(popup_handle)
            logger.info(f"Apple ID 登入視窗已開啟：{driver.current_url}")
        except Exception:
            pass

        # 等待彈窗關閉（用戶完成登入）
        while time.time() - start < timeout:
            if popup_handle not in driver.window_handles:
                logger.info("Apple ID 登入視窗已關閉")
                break
            elapsed = int(time.time() - start)
            if elapsed > 0 and elapsed % 30 == 0:
                logger.info(f"等待登入中... ({elapsed}s)")
            time.sleep(2)

        # 切回主視窗
        try:
            driver.switch_to.window(main_window)
        except Exception:
            pass
    else:
        # 行內登入（modal overlay）：無新視窗，直接等待 token
        logger.info("偵測到行內登入 modal，請在瀏覽器中完成登入")

    # ── 等待 token 寫入 MusicKit（行內登入或 popup 後） ──
    # 用戶完成登入後 MusicKit 異步寫入 token，持續輪詢直到取得或逾時
    while time.time() - start < timeout:
        try:
            result = driver.execute_script(_EXTRACT_TOKENS_JS)
            if result and result.get("userToken"):
                return result["userToken"]
        except Exception:
            pass

        elapsed = int(time.time() - start)
        if elapsed > 0 and elapsed % 30 == 0:
            logger.info(f"等待登入完成... ({elapsed}s)")
        time.sleep(3)

    logger.warning("等待登入逾時")
    return None


def get_tokens(driver: webdriver.Chrome) -> tuple[str, str] | tuple[None, None]:
    """開啟 music.apple.com，提取 developer token 與 user token。

    流程：
    1. 載入 music.apple.com，等待 MusicKit 初始化（devToken 此時已可取得）
    2. 若 isAuthorized（session 有效），直接回傳兩個 token
    3. 若未授權，呼叫 MusicKit.authorize() 觸發 Apple ID 登入，等待完成

    Returns:
        (dev_token, user_token) 或 (None, None)
    """
    logger.info(f"開啟 {MUSIC_APPLE_URL} 以取得 Apple Music token...")
    driver.get(MUSIC_APPLE_URL)

    # 等待頁面初步載入
    try:
        WebDriverWait(driver, 20).until(
            EC.presence_of_element_located((By.TAG_NAME, "body"))
        )
    except TimeoutException:
        pass

    # 等待 MusicKit 初始化（通常 5–10 秒）
    logger.info("等待 MusicKit 初始化...")
    mk_ready = False
    for attempt in range(20):
        time.sleep(2)
        try:
            result = driver.execute_script(_EXTRACT_TOKENS_JS)
            if result and result.get("hasMusicKit") and result.get("devToken"):
                mk_ready = True
                logger.info(f"MusicKit 已初始化（attempt {attempt + 1}）")
                break
        except Exception:
            pass

    if not mk_ready:
        logger.error("MusicKit 未能初始化")
        save_debug_screenshot(driver, "musickit_init")
        return None, None

    # 嘗試取得兩個 token（已授權時立即可得）
    result = driver.execute_script(_EXTRACT_TOKENS_JS)
    if result and result.get("devToken") and result.get("userToken"):
        logger.info("Apple Music session 有效，直接取得 token")
        return result["devToken"], result["userToken"]

    dev_token = result.get("devToken") if result else None
    if not dev_token:
        logger.error("無法取得 developer token")
        return None, None

    if not _interactive_login_allowed():
        raise AppleMusicAuthRequiredError(
            "Apple Music 需要重新登入，但目前為非互動環境，已略過同步。"
            f" 請在終端手動執行一次並完成授權，或設定 {ALLOW_INTERACTIVE_LOGIN_ENV}=1 覆寫。"
        )

    # 未授權：點擊 Sign In 按鈕觸發 Apple ID 登入
    logger.info("尚未授權，嘗試點擊 Sign In 按鈕...")
    print("\n" + "=" * 60)
    print("  請在彈出的視窗中登入 Apple ID")
    print("  完成後程式將自動繼續")
    print("=" * 60 + "\n")

    _click_sign_in(driver)

    # 等待用戶完成登入
    user_token = _wait_for_user_token(driver)
    if not user_token:
        logger.error("等待登入逾時")
        save_debug_screenshot(driver, "apple_music_login")
        return None, None

    logger.info("Apple ID 登入完成，成功取得 user token")
    return dev_token, user_token


# ── Apple Music API 呼叫 ──


def _make_headers(dev_token: str, user_token: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {dev_token}",
        "Music-User-Token": user_token,
    }


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
    # 依 dateAdded 降冪取最新
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


# ── 主入口 ──


def import_to_apple_music(
    csv_path: str,
    keep_browser_open: bool = False,
    playlist_name: str | None = None,
) -> bool:
    """將 CSV 檔案透過 Apple Music API 直接匯入播放清單。

    Args:
        csv_path: CSV 檔案路徑（欄位：Artist, Title）
        keep_browser_open: 完成後是否保持瀏覽器開啟（預設自動關閉）
        playlist_name: 目標播放清單名稱（若不指定則使用 CSV 檔名）

    Returns:
        是否成功（有任何曲目成功加入即為 True）
    """
    csv_path = str(Path(csv_path).resolve())
    if not Path(csv_path).exists():
        logger.error(f"CSV 檔案不存在：{csv_path}")
        return False

    # 讀取 CSV
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

    print("\n  正在啟動瀏覽器...")
    driver = create_driver()
    try:
        # ── 取得 token ──
        dev_token, user_token = get_tokens(driver)
        if not dev_token or not user_token:
            logger.error("無法取得 Apple Music token")
            return False

        storefront = get_storefront(dev_token, user_token)

        # ── 搜尋曲目 ──
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

        # ── 刪除舊同名歌單（API 層） ──
        old_id = _get_existing_playlist_id(name, dev_token, user_token)
        if old_id:
            if _delete_playlist_by_id(old_id, dev_token, user_token):
                logger.info(f"已刪除舊播放清單「{name}」（ID: {old_id}）")
            else:
                logger.warning("舊播放清單刪除失敗，繼續建立新版本")
            time.sleep(2)

        # ── 建立新歌單 ──
        playlist_id = create_playlist(name, dev_token, user_token)
        if not playlist_id:
            return False

        # ── 加入曲目 ──
        added = add_tracks_to_playlist(playlist_id, found_ids, dev_token, user_token)

        print(
            f"\n  匯入完成！{added}/{len(tracks)} 首已加入"
            f"（{len(not_found)} 首未在 Apple Music 找到）"
        )
        print("  請至 Apple Music 確認播放清單。\n")
        return added > 0

    except AppleMusicAuthRequiredError:
        raise
    except Exception as e:
        logger.error(f"匯入失敗：{e}", exc_info=True)
        return False
    finally:
        if not keep_browser_open:
            driver.quit()
            logger.info("瀏覽器已關閉")
