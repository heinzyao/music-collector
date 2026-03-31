"""Apple Music 播放清單管理：刪除、改名、去重。

支援兩種策略：
1. MusicKit JS / fetch API（透過瀏覽器執行）
2. macOS Music.app（透過 osascript/AppleScript fallback）
"""

import logging
import subprocess
import sys
import time
from pathlib import Path

from selenium import webdriver

from .browser import APPLE_MUSIC_API_JS, save_debug_screenshot

logger = logging.getLogger(__name__)


def _escape_applescript(s: str) -> str:
    """AppleScript 字串中的反斜線與雙引號轉義。"""
    return s.replace("\\", "\\\\").replace('"', '\\"')


def _find_playlist_in_music_app(name: str) -> bool:
    """檢查 Music.app 中是否存在指定名稱的播放清單。"""
    escaped = _escape_applescript(name)
    script = (
        'tell application "Music"\n'
        f'  set matches to (every playlist whose name is "{escaped}")\n'
        '  if (count of matches) > 0 then return "found"\n'
        '  return "not_found"\n'
        "end tell"
    )
    try:
        result = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True,
            text=True,
            timeout=10,
        )
        return result.stdout.strip() == "found"
    except Exception:
        return False


def _delete_via_music_app(name: str) -> None:
    """透過 macOS Music.app (AppleScript) 刪除同名播放清單。"""
    if not _find_playlist_in_music_app(name):
        logger.info(f"Music.app 中無同名播放清單「{name}」，跳過刪除")
        return

    escaped = _escape_applescript(name)
    script = (
        'tell application "Music"\n'
        f'  set matches to (every playlist whose name is "{escaped}")\n'
        "  repeat with p in matches\n"
        "    delete p\n"
        "  end repeat\n"
        f"  return (count of matches) as text\n"
        "end tell"
    )
    try:
        result = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True,
            text=True,
            timeout=15,
        )
        count = result.stdout.strip()
        if result.returncode == 0 and count:
            logger.info(f"已透過 Music.app 刪除 {count} 個同名播放清單「{name}」")
        else:
            logger.warning(f"Music.app 刪除失敗：{result.stderr.strip()}")
    except subprocess.TimeoutExpired:
        logger.warning("Music.app 刪除逾時")
    except Exception as e:
        logger.warning(f"Music.app 刪除例外：{e}")


def _rename_via_music_app(target_name: str, csv_stem: str) -> None:
    """透過 macOS Music.app (AppleScript) 改名播放清單。

    TuneMyMusic 建立的播放清單會透過 iCloud 同步至 Music.app，
    此函式等待同步完成後將播放清單改名。
    """
    # 候選名稱
    candidates = ["My playlist", "My Playkist"]
    if csv_stem and csv_stem != target_name:
        candidates.append(csv_stem)

    # 等待 iCloud 同步（漸進式退避，最多約 3 分鐘）
    logger.info("等待 Music.app iCloud 同步...")
    found_name = None
    wait_intervals = [5, 5, 5, 10, 10, 10, 15, 15, 20, 20, 25, 30]  # 共約 170 秒
    for attempt, wait in enumerate(wait_intervals):
        for name in candidates:
            if _find_playlist_in_music_app(name):
                found_name = name
                break
        if found_name:
            break
        logger.debug(
            f"同步等待第 {attempt + 1}/{len(wait_intervals)} 次，{wait} 秒後重試"
        )
        time.sleep(wait)

    if not found_name:
        # 也確認目標名稱是否已存在（可能已經是正確的）
        if _find_playlist_in_music_app(target_name):
            logger.info(f"Apple Music 播放清單名稱已正確：{target_name}")
            return
        logger.warning(f"Music.app 中找不到候選播放清單 {candidates}，可能尚未同步完成")
        return

    # 改名
    escaped_old = _escape_applescript(found_name)
    escaped_new = _escape_applescript(target_name)
    rename_script = (
        'tell application "Music"\n'
        f'  set targetPlaylist to first playlist whose name is "{escaped_old}"\n'
        f'  set name of targetPlaylist to "{escaped_new}"\n'
        '  return "ok"\n'
        "end tell"
    )
    try:
        result = subprocess.run(
            ["osascript", "-e", rename_script],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.stdout.strip() == "ok":
            logger.info(
                f"已透過 Music.app 將播放清單「{found_name}」改名為「{target_name}」"
            )
        else:
            logger.warning(f"Music.app 改名失敗：{result.stderr.strip()}")
    except subprocess.TimeoutExpired:
        logger.warning("Music.app 改名逾時")
    except Exception as e:
        logger.warning(f"Music.app 改名例外：{e}")


def _deduplicate_via_music_app(name: str) -> None:
    """透過 macOS Music.app (AppleScript) 刪除同名播放清單的重複項目。"""
    escaped = _escape_applescript(name)
    script = (
        'tell application "Music"\n'
        f'  set matches to (every playlist whose name is "{escaped}")\n'
        "  set matchCount to count of matches\n"
        '  if matchCount < 2 then return "0"\n'
        "  set deletedCount to 0\n"
        "  repeat while matchCount > 1\n"
        "    delete item 1 of matches\n"
        "    set deletedCount to deletedCount + 1\n"
        f'    set matches to (every playlist whose name is "{escaped}")\n'
        "    set matchCount to count of matches\n"
        "  end repeat\n"
        "  return deletedCount as text\n"
        "end tell"
    )
    try:
        result = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True,
            text=True,
            timeout=30,
        )
        count = result.stdout.strip()
        if result.returncode == 0 and count and count != "0":
            logger.info(f"已透過 Music.app 刪除 {count} 個重複播放清單「{name}」")
        elif result.returncode == 0:
            logger.info(f"Music.app 中無重複播放清單「{name}」")
        else:
            logger.warning(f"Music.app 合併失敗：{result.stderr.strip()}")
    except subprocess.TimeoutExpired:
        logger.warning("Music.app 合併逾時")
    except Exception as e:
        logger.warning(f"Music.app 合併例外：{e}")


def delete_existing_playlist(driver: webdriver.Chrome, name: str) -> None:
    """刪除 Apple Music 中同名的現有播放清單，避免重複建立。

    TuneMyMusic 每次轉移都會建立新播放清單，無法更新現有的。
    此函式在轉移前透過 Apple Music API 找到並刪除同名播放清單，
    讓新建的播放清單成為唯一副本。

    策略：
    1. MusicKit JS / fetch API（若可用）
    2. macOS Music.app（透過 osascript/AppleScript）
    """
    web_api_succeeded = False
    try:
        result = driver.execute_script(
            APPLE_MUSIC_API_JS
            + """
            var targetName = arguments[0];

            if (!canUseMusicKitApi && !canUseFetch) {
                return {status: 'no_api', debug: _apiDebugInfo()};
            }

            try {
                var data = await apiGet('/v1/me/library/playlists?limit=100');
                var playlists = data.data || [];

                // 找到同名播放清單
                var matches = playlists.filter(function(p) {
                    return p.attributes &&
                           p.attributes.name === targetName;
                });

                if (matches.length === 0) {
                    return {status: 'skip', reason: 'No matching playlist found'};
                }

                // 刪除所有同名播放清單
                var deleted = [];
                for (var i = 0; i < matches.length; i++) {
                    var playlistId = matches[i].id;
                    try {
                        await apiDelete(
                            '/v1/me/library/playlists/' + playlistId
                        );
                        deleted.push(playlistId);
                    } catch(e) {
                        // 單一刪除失敗不影響其他
                    }
                }

                return {
                    status: 'ok',
                    found: matches.length,
                    deleted: deleted.length,
                    ids: deleted,
                    mode: canUseMusicKitApi ? 'musickit' : 'fetch'
                };
            } catch(e) {
                return {status: 'error', reason: e.toString()};
            }
        """,
            name,
        )

        if result:
            status = result.get("status", "unknown")
            if status == "ok":
                found = result.get("found", 0)
                deleted = result.get("deleted", 0)
                mode = result.get("mode", "?")
                logger.info(
                    f"已刪除 {deleted}/{found} 個同名 Apple Music 播放清單"
                    f"「{name}」（透過 {mode}）"
                )
                web_api_succeeded = True
            elif status == "skip":
                reason = result.get("reason", "")
                logger.info(f"跳過刪除 Apple Music 播放清單：{reason}")
                web_api_succeeded = True  # 無需 fallback
            elif status == "no_api":
                logger.info("MusicKit JS 不可用，將使用 Music.app 刪除")
            else:
                reason = result.get("reason", "")
                logger.warning(f"Web API 刪除失敗（{reason}），嘗試 Music.app")

    except Exception as e:
        logger.debug(f"Web API 刪除例外：{e}")

    if web_api_succeeded:
        return

    # --- Fallback: macOS Music.app (osascript) ---
    if sys.platform != "darwin":
        logger.warning("非 macOS 環境，無法透過 Music.app 刪除")
        return

    _delete_via_music_app(name)


def rename_playlist(driver: webdriver.Chrome, target_name: str, csv_path: str) -> None:
    """將 TuneMyMusic 新建的 Apple Music 播放清單改名為正確名稱。

    TuneMyMusic 建立播放清單時使用預設名稱（如 "My playlist"）而非 CSV 檔名
    或使用者指定的名稱。

    改名策略（依優先順序）：
    1. MusicKit JS API（若 TuneMyMusic 有設定 MusicKit 實例）
    2. 提取 developer token + user token，直接用 fetch 呼叫 Apple Music REST API
    3. macOS Music.app（透過 osascript/AppleScript，等待 iCloud 同步後改名）

    播放清單搜尋策略：
    1. 名稱為 "My playlist" 或 "My Playkist"（TuneMyMusic 預設名稱）
    2. 名稱為 CSV 檔名（不含副檔名）
    3. 若 target_name 已存在則跳過（名稱已正確）
    """
    csv_stem = Path(csv_path).stem

    # --- 策略 1 & 2: MusicKit JS / fetch ---
    web_api_succeeded = False
    try:
        result = driver.execute_script(
            APPLE_MUSIC_API_JS
            + """
            var targetName = arguments[0];
            var csvStem = arguments[1];

            if (!canUseMusicKitApi && !canUseFetch) {
                return {status: 'no_api'};
            }

            try {
                var data = await apiGet('/v1/me/library/playlists?limit=100');
                var playlists = data.data || [];

                var alreadyCorrect = playlists.some(function(p) {
                    return p.attributes && p.attributes.name === targetName;
                });
                if (alreadyCorrect) {
                    return {status: 'skip', reason: 'Playlist already has correct name'};
                }

                var candidateNames = ['My playlist', 'My Playkist'];
                if (csvStem && csvStem !== targetName) {
                    candidateNames.push(csvStem);
                }

                var toRename = null;
                for (var c = 0; c < candidateNames.length; c++) {
                    for (var i = 0; i < playlists.length; i++) {
                        if (playlists[i].attributes &&
                            playlists[i].attributes.name === candidateNames[c]) {
                            toRename = playlists[i];
                            break;
                        }
                    }
                    if (toRename) break;
                }

                if (!toRename) {
                    return {status: 'skip', reason: 'No candidate playlist found',
                            searched: candidateNames};
                }

                var oldName = toRename.attributes.name;
                var playlistId = toRename.id;

                await apiPatch(
                    '/v1/me/library/playlists/' + playlistId,
                    { attributes: { name: targetName } }
                );

                return {status: 'ok', oldName: oldName, newName: targetName,
                        mode: canUseMusicKitApi ? 'musickit' : 'fetch'};
            } catch(e) {
                return {status: 'error', reason: e.toString()};
            }
        """,
            target_name,
            csv_stem,
        )

        if result:
            status = result.get("status", "unknown")
            if status == "ok":
                old = result.get("oldName", "?")
                mode = result.get("mode", "?")
                logger.info(
                    f"已將 Apple Music 播放清單「{old}」改名為"
                    f"「{target_name}」（透過 {mode}）"
                )
                web_api_succeeded = True
            elif status == "skip":
                reason = result.get("reason", "")
                logger.info(f"跳過改名 Apple Music 播放清單：{reason}")
                web_api_succeeded = True  # 不需要 fallback
            elif status == "no_api":
                logger.info("MusicKit JS 不可用，將使用 Music.app 改名")
            else:
                reason = result.get("reason", "")
                logger.warning(f"Web API 改名失敗（{reason}），嘗試 Music.app")
    except Exception as e:
        logger.debug(f"Web API 改名例外：{e}")

    if web_api_succeeded:
        return

    # --- 策略 3: macOS Music.app (osascript) ---
    if sys.platform != "darwin":
        logger.warning("非 macOS 環境，無法透過 Music.app 改名")
        return

    _rename_via_music_app(target_name, csv_stem)


def deduplicate_playlists(driver: webdriver.Chrome, name: str) -> None:
    """合併同名 Apple Music 播放清單，只保留最新的一個。

    TuneMyMusic 每次轉移都會建立新播放清單，若先前的刪除步驟失敗，
    會導致出現多個同名播放清單。此函式在轉移完成後清理重複項目。

    策略（依優先順序）：
    1. MusicKit JS / fetch API（含分頁，取得所有播放清單）
    2. macOS Music.app（透過 osascript/AppleScript）
    """
    web_api_succeeded = False
    try:
        result = driver.execute_script(
            APPLE_MUSIC_API_JS
            + """
            var targetName = arguments[0];

            if (!canUseMusicKitApi && !canUseFetch) {
                return {status: 'no_api', debug: _apiDebugInfo()};
            }

            try {
                // 分頁取得所有播放清單
                var allPlaylists = [];
                var offset = 0;
                var limit = 100;
                while (true) {
                    var data = await apiGet(
                        '/v1/me/library/playlists?limit=' + limit
                        + '&offset=' + offset
                    );
                    var page = data.data || [];
                    allPlaylists = allPlaylists.concat(page);
                    if (page.length < limit || !data.next) break;
                    offset += limit;
                }

                // 找出所有同名播放清單
                var matches = allPlaylists.filter(function(p) {
                    return p.attributes &&
                           p.attributes.name === targetName;
                });

                if (matches.length <= 1) {
                    return {
                        status: 'skip',
                        reason: 'No duplicates (found ' + matches.length + ')'
                    };
                }

                // 依 dateAdded 降冪排序，保留最新的
                matches.sort(function(a, b) {
                    var dateA = (a.attributes.dateAdded || '');
                    var dateB = (b.attributes.dateAdded || '');
                    return dateB.localeCompare(dateA);
                });

                var keep = matches[0];
                var deleted = [];
                for (var i = 1; i < matches.length; i++) {
                    try {
                        await apiDelete(
                            '/v1/me/library/playlists/' + matches[i].id
                        );
                        deleted.push(matches[i].id);
                    } catch(e) {
                        // 單一刪除失敗不影響其他
                    }
                }

                return {
                    status: 'ok',
                    kept: keep.id,
                    found: matches.length,
                    deleted: deleted.length,
                    mode: canUseMusicKitApi ? 'musickit' : 'fetch'
                };
            } catch(e) {
                return {status: 'error', reason: e.toString()};
            }
        """,
            name,
        )

        if result:
            status = result.get("status", "unknown")
            if status == "ok":
                found = result.get("found", 0)
                deleted = result.get("deleted", 0)
                mode = result.get("mode", "?")
                logger.info(
                    f"已合併 Apple Music 播放清單「{name}」："
                    f"找到 {found} 個，刪除 {deleted} 個重複（透過 {mode}）"
                )
                web_api_succeeded = True
            elif status == "skip":
                reason = result.get("reason", "")
                logger.info(f"無需合併 Apple Music 播放清單：{reason}")
                web_api_succeeded = True
            elif status == "no_api":
                logger.info("MusicKit JS 不可用，將使用 Music.app 合併")
            else:
                reason = result.get("reason", "")
                logger.warning(f"Web API 合併失敗（{reason}），嘗試 Music.app")

    except Exception as e:
        logger.debug(f"Web API 合併例外：{e}")

    if web_api_succeeded:
        return

    # --- Fallback: macOS Music.app (osascript) ---
    if sys.platform != "darwin":
        logger.warning("非 macOS 環境，無法透過 Music.app 合併")
        return

    _deduplicate_via_music_app(name)
