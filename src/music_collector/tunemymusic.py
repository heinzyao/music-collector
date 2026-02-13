"""TuneMyMusic 自動化模組：使用 Selenium 將 CSV 匯入 Apple Music。

此模組自動化 TuneMyMusic 網站的操作流程：
1. 上傳 CSV 檔案
2. 確認曲目對應
3. 選擇 Apple Music 作為目標
4. 等待使用者手動完成 Apple ID 授權
5. 完成匯入

使用方式：
    from .tunemymusic import import_to_apple_music
    import_to_apple_music("/path/to/export.csv")
"""

import logging
import time
from datetime import datetime
from pathlib import Path

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from selenium.common.exceptions import TimeoutException, NoSuchElementException

logger = logging.getLogger(__name__)

# TuneMyMusic 網址
TUNEMYMUSIC_URL = "https://www.tunemymusic.com/"

# 等待時間設定
WAIT_TIMEOUT = 30  # 一般元素等待秒數
AUTH_TIMEOUT = 300  # Apple Music 授權等待秒數（5 分鐘）


def _save_debug_screenshot(driver: webdriver.Chrome, name: str) -> None:
    """儲存除錯截圖至 data/ 目錄。"""
    try:
        debug_dir = Path("data")
        debug_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = debug_dir / f"debug_{name}_{timestamp}.png"
        driver.save_screenshot(str(path))
        logger.info(f"已儲存除錯截圖：{path}")
    except Exception as e:
        logger.debug(f"無法儲存截圖：{e}")


def _dismiss_cookie_consent(driver: webdriver.Chrome) -> None:
    """嘗試關閉 cookie 同意彈窗（若存在）。

    TuneMyMusic 使用 cookie consent overlay，會阻擋所有按鈕互動。
    此函式靜默處理——找不到彈窗不視為錯誤。
    """
    consent_selectors = [
        # 常見 cookie consent 按鈕 selector
        "//button[normalize-space(text())='OK']",
        "//button[normalize-space(text())='Accept']",
        "//button[normalize-space(text())='Accept All']",
        "//button[normalize-space(text())='Accept all']",
        "//button[normalize-space(text())='I agree']",
        "//button[normalize-space(text())='Got it']",
        "//button[normalize-space(text())='Agree']",
        "//button[contains(@class, 'consent')]",
        "//button[contains(@class, 'cookie')]",
        "//a[normalize-space(text())='OK']",
        "//a[normalize-space(text())='Accept']",
        # CMP (Consent Management Platform) 常見 selector
        "[class*='consent'] button",
        "[class*='cookie'] button",
        "[id*='consent'] button",
        "[id*='cookie'] button",
        "#onetrust-accept-btn-handler",
        ".cc-accept",
        ".cc-btn.cc-dismiss",
    ]

    for selector in consent_selectors:
        try:
            by = By.XPATH if selector.startswith("//") else By.CSS_SELECTOR
            element = WebDriverWait(driver, 3).until(
                EC.element_to_be_clickable((by, selector))
            )
            element.click()
            logger.info(f"已關閉 cookie 同意彈窗（selector: {selector}）")
            time.sleep(1)  # 等待 overlay 消失
            return
        except (TimeoutException, NoSuchElementException):
            continue

    logger.debug("未發現 cookie 同意彈窗（或已關閉）")


def _create_driver() -> webdriver.Chrome:
    """建立 Chrome WebDriver。

    針對 TuneMyMusic/Apple MusicKit JS 的「Private mode isn't supported」問題，
    需要確保瀏覽器不被偵測為無痕模式。MusicKit JS 會透過 IndexedDB、
    Service Worker、storage estimate 等 API 來判斷是否為無痕模式。
    """
    options = Options()
    # 不使用 headless 模式，因為需要使用者手動授權
    options.add_argument("--start-maximized")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)

    # 設定持久化使用者資料目錄（避免每次都是空白 profile 被偵測為無痕模式）
    user_data_dir = Path("data/browser_profile").resolve()
    user_data_dir.mkdir(parents=True, exist_ok=True)
    options.add_argument(f"user-data-dir={user_data_dir}")

    # 防止無痕模式偵測：確保 storage/IndexedDB/Service Worker 正常運作
    options.add_argument("--disable-features=IsolateOrigins,site-per-process")
    options.add_argument("--enable-features=NetworkService,NetworkServiceInProcess")

    # 允許第三方 cookies（Apple MusicKit JS OAuth 需要）
    options.add_argument("--disable-features=SameSiteByDefaultCookies")
    options.add_argument("--disable-site-isolation-trials")

    # 啟用必要的 Web API（MusicKit JS 依賴 IndexedDB 與 Service Worker）
    prefs = {
        "profile.default_content_setting_values.cookies": 1,  # 允許所有 cookies
        "profile.block_third_party_cookies": False,
        "profile.cookie_controls_mode": 0,  # 允許所有 cookies
    }
    options.add_experimental_option("prefs", prefs)

    driver = webdriver.Chrome(options=options)

    # 隱藏 webdriver 特徵（多重防護）
    driver.execute_cdp_cmd(
        "Page.addScriptToEvaluateOnNewDocument",
        {
            "source": """
                // 隱藏 navigator.webdriver
                Object.defineProperty(navigator, 'webdriver', {get: () => undefined});

                // 偽裝 navigator.plugins（無痕模式下 plugins 可能為空）
                Object.defineProperty(navigator, 'plugins', {
                    get: () => [1, 2, 3, 4, 5],
                });

                // 偽裝 navigator.languages
                Object.defineProperty(navigator, 'languages', {
                    get: () => ['zh-TW', 'zh', 'en-US', 'en'],
                });

                // 確保 storage API 回報充足空間（無痕模式下配額極低）
                if (navigator.storage && navigator.storage.estimate) {
                    const originalEstimate = navigator.storage.estimate.bind(navigator.storage);
                    navigator.storage.estimate = async () => {
                        const result = await originalEstimate();
                        // 無痕模式下 quota 通常 < 120MB，正常模式 > 1GB
                        if (result.quota < 500 * 1024 * 1024) {
                            result.quota = 4 * 1024 * 1024 * 1024;  // 偽裝為 4GB
                        }
                        return result;
                    };
                }
            """
        },
    )
    return driver


def _wait_and_click(
    driver: webdriver.Chrome,
    selector: str,
    by: By = By.CSS_SELECTOR,
    timeout: int = WAIT_TIMEOUT,
) -> bool:
    """等待元素出現並點擊。"""
    try:
        element = WebDriverWait(driver, timeout).until(
            EC.element_to_be_clickable((by, selector))
        )
        element.click()
        return True
    except TimeoutException:
        logger.warning(f"等待元素逾時：{selector}")
        return False


def _wait_for_element(
    driver: webdriver.Chrome,
    selector: str,
    by: By = By.CSS_SELECTOR,
    timeout: int = WAIT_TIMEOUT,
):
    """等待元素出現。"""
    try:
        return WebDriverWait(driver, timeout).until(
            EC.presence_of_element_located((by, selector))
        )
    except TimeoutException:
        return None


def _upload_file(driver: webdriver.Chrome, csv_path: str) -> bool:
    """上傳 CSV 檔案。

    TuneMyMusic 使用 React 動態渲染 dropzone 元件，
    input[type='file'] 在點擊「Upload file」來源後才會由 React 建立。
    需要等待 SPA 頁面切換與 React hydration 完成。
    """
    try:
        # 等待 SPA 導航（URL 可能變更至 /transfer）
        for _ in range(WAIT_TIMEOUT):
            if "/transfer" in driver.current_url:
                logger.info(f"已導航至 {driver.current_url}")
                break
            time.sleep(1)

        # 使用 JavaScript 輪詢 input[type='file']，
        # 因為 React dropzone 元件可能延遲掛載
        file_input = None
        for attempt in range(WAIT_TIMEOUT):
            # 嘗試用 JS 直接查找（包含隱藏元素）
            inputs = driver.execute_script(
                "return document.querySelectorAll('input[type=\"file\"]')"
            )
            if inputs:
                file_input = inputs[0]
                break

            # 嘗試點擊 dropzone 區域以觸發元件渲染
            if attempt == 5:
                try:
                    dropzone = driver.find_element(
                        By.XPATH,
                        "//*[contains(text(), 'Choose a file') or "
                        "contains(text(), 'drag') or "
                        "contains(text(), '選擇檔案') or "
                        "contains(text(), '拖曳')]",
                    )
                    dropzone.click()
                    logger.info("已點擊上傳區域")
                except NoSuchElementException:
                    pass

            time.sleep(1)

        if file_input is None:
            # 最終嘗試：用 Selenium 標準方式等待
            file_input = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "input[type='file']"))
            )

        # 確保 input 可互動（移除所有隱藏屬性與限制）
        driver.execute_script(
            "var el = arguments[0];"
            "el.style.display = 'block';"
            "el.style.visibility = 'visible';"
            "el.style.opacity = '1';"
            "el.style.width = '200px';"
            "el.style.height = '30px';"
            "el.style.position = 'fixed';"
            "el.style.top = '0';"
            "el.style.left = '0';"
            "el.style.zIndex = '99999';"
            "el.removeAttribute('hidden');"
            "el.removeAttribute('aria-hidden');"
            "el.className = '';",
            file_input,
        )
        time.sleep(0.5)  # 讓瀏覽器重新 layout
        file_input.send_keys(csv_path)
        logger.info(f"已上傳檔案：{csv_path}")
        return True
    except (TimeoutException, Exception) as e:
        # 記錄頁面狀態以便除錯
        logger.error(f"找不到檔案上傳欄位：{e}")
        logger.debug(f"當前 URL：{driver.current_url}")
        try:
            body_text = driver.execute_script(
                "return document.body ? document.body.innerText.substring(0, 500) : ''"
            )
            logger.debug(f"頁面內容片段：{body_text}")
        except Exception:
            pass
        _save_debug_screenshot(driver, "upload_file")
        return False


def _click_continue_button(driver: webdriver.Chrome) -> bool:
    """點擊繼續/確認按鈕。

    TuneMyMusic 各步驟的「Continue」或「Choose Destination」按鈕
    統一使用 name='stickyButton' 屬性，這是最穩定的 selector。
    按鈕文字在不同步驟會變化：
    - Step 2 (field mapping): "Continue"
    - Step 2 (playlist selection): "Choose Destination"
    """
    selectors = [
        # 最穩定：所有步驟的 Continue/Choose Destination 共用此 name
        "button[name='stickyButton']",
        "//*[normalize-space(text())='Continue']",
        "//*[normalize-space(text())='Choose Destination']",
        "//*[normalize-space(text())='繼續']",
        "//*[normalize-space(text())='選擇目的地']",
        "//*[contains(text(), 'Next')]",
    ]

    for selector in selectors:
        try:
            by = By.XPATH if selector.startswith("//") else By.CSS_SELECTOR
            element = WebDriverWait(driver, 5).until(
                EC.element_to_be_clickable((by, selector))
            )
            btn_text = element.text.strip() if element.text else "(no text)"
            element.click()
            logger.info(f"已點擊按鈕：{btn_text}")
            time.sleep(1)  # 等待頁面轉換
            return True
        except TimeoutException:
            continue

    return False


def _set_playlist_name(driver: webdriver.Chrome, name: str) -> None:
    """設定 TuneMyMusic 的目標播放清單名稱。

    TuneMyMusic 使用 CSV 檔名作為預設播放清單名稱，
    但在「Choose Destination」步驟前有可編輯的 input 欄位可以修改。
    此函式找到該欄位並設定為指定名稱。
    """
    # 嘗試多種 selector 找到播放清單名稱輸入欄位
    name_selectors = [
        # input 類型的編輯欄位
        "input[name='playlistName']",
        "input[name='playlist_name']",
        "input[name='playlist-name']",
        "input[placeholder*='playlist']",
        "input[placeholder*='Playlist']",
        # contentEditable 類型的編輯欄位
        "[contenteditable='true']",
        # 通用 input（排除 file input 和 hidden）
        "input[type='text']",
    ]

    for selector in name_selectors:
        try:
            elements = driver.find_elements(By.CSS_SELECTOR, selector)
            for element in elements:
                # 跳過不可見或不相關的元素
                if not element.is_displayed():
                    continue

                # 清除並設定新名稱
                current_value = element.get_attribute("value") or element.text
                if current_value:
                    logger.info(
                        f"找到播放清單名稱欄位（目前值：{current_value}），"
                        f"設定為：{name}"
                    )

                # 使用 JavaScript 清除並設定值（比 clear() + send_keys() 更可靠）
                is_input = element.tag_name.lower() == "input"
                if is_input:
                    driver.execute_script(
                        "var el = arguments[0];"
                        "el.focus();"
                        "el.value = '';"
                        "el.value = arguments[1];"
                        "el.dispatchEvent(new Event('input', {bubbles: true}));"
                        "el.dispatchEvent(new Event('change', {bubbles: true}));",
                        element,
                        name,
                    )
                else:
                    # contentEditable
                    driver.execute_script(
                        "var el = arguments[0];"
                        "el.focus();"
                        "el.textContent = arguments[1];"
                        "el.dispatchEvent(new Event('input', {bubbles: true}));",
                        element,
                        name,
                    )

                logger.info(f"已設定播放清單名稱為：{name}")
                return
        except (NoSuchElementException, Exception):
            continue

    # 最後嘗試：用 JavaScript 搜尋所有可能的 input 和 editable 元素
    try:
        result = driver.execute_script("""
            // 尋找包含檔名的 input
            var inputs = document.querySelectorAll('input[type="text"], input:not([type])');
            for (var i = 0; i < inputs.length; i++) {
                var input = inputs[i];
                if (input.offsetParent !== null && input.value && input.value.length > 0) {
                    input.focus();
                    input.value = '';
                    input.value = arguments[0];
                    input.dispatchEvent(new Event('input', {bubbles: true}));
                    input.dispatchEvent(new Event('change', {bubbles: true}));
                    return 'input:' + i;
                }
            }
            // 尋找 contentEditable 元素
            var editables = document.querySelectorAll('[contenteditable="true"]');
            for (var i = 0; i < editables.length; i++) {
                var el = editables[i];
                if (el.offsetParent !== null && el.textContent.trim().length > 0) {
                    el.focus();
                    el.textContent = arguments[0];
                    el.dispatchEvent(new Event('input', {bubbles: true}));
                    return 'editable:' + i;
                }
            }
            return null;
        """, name)

        if result:
            logger.info(f"已透過 JS 設定播放清單名稱為：{name}（元素：{result}）")
            return
    except Exception as e:
        logger.debug(f"JS 搜尋播放清單名稱欄位失敗：{e}")

    logger.warning(f"找不到播放清單名稱編輯欄位，將使用 CSV 檔名作為播放清單名稱")
    _save_debug_screenshot(driver, "set_playlist_name")


def _delete_existing_apple_music_playlist(driver: webdriver.Chrome, name: str) -> None:
    """刪除 Apple Music 中同名的現有播放清單，避免重複建立。

    TuneMyMusic 每次轉移都會建立新播放清單，無法更新現有的。
    此函式在轉移前透過 TuneMyMusic 已載入的 MusicKit JS API
    找到並刪除同名播放清單，讓新建的播放清單成為唯一副本。

    若 MusicKit JS 不可用或無同名播放清單，靜默跳過。
    """
    try:
        result = driver.execute_script("""
            var targetName = arguments[0];

            // 取得 MusicKit 實例
            var music = null;
            if (typeof MusicKit !== 'undefined') {
                try { music = MusicKit.getInstance(); } catch(e) {}
            }
            if (!music) {
                // TuneMyMusic 可能把實例存在全域變數
                if (window.music) music = window.music;
            }
            if (!music || !music.api) {
                return {status: 'skip', reason: 'MusicKit JS not available'};
            }

            // 列出使用者的播放清單
            try {
                var response = await music.api.music('/v1/me/library/playlists');
                var playlists = response.data.data || [];

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
                        await music.api.music(
                            '/v1/me/library/playlists/' + playlistId,
                            {},
                            {method: 'DELETE'}
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
                    ids: deleted
                };
            } catch(e) {
                return {status: 'error', reason: e.toString()};
            }
        """, name)

        if not result:
            logger.debug("MusicKit JS 回傳空結果")
            return

        status = result.get("status", "unknown")
        if status == "ok":
            found = result.get("found", 0)
            deleted = result.get("deleted", 0)
            logger.info(
                f"已刪除 {deleted}/{found} 個同名 Apple Music 播放清單「{name}」"
            )
        elif status == "skip":
            reason = result.get("reason", "")
            logger.info(f"跳過刪除 Apple Music 播放清單：{reason}")
        else:
            reason = result.get("reason", "")
            logger.warning(f"刪除 Apple Music 播放清單失敗：{reason}")

    except Exception as e:
        logger.debug(f"刪除 Apple Music 播放清單時發生例外（靜默跳過）：{e}")


def _select_upload_source(driver: webdriver.Chrome) -> bool:
    """選擇「上傳檔案」作為來源。"""
    # name 屬性最穩定（不受語系與 CSS 模組 hash 影響）
    selectors = [
        "button[name='FromFile']",
        "button[title='Upload file']",
        "button[aria-label='Upload file']",
        "//button[contains(@title, 'Upload')]",
        "//button[contains(@title, '上傳')]",
        "//button[contains(@aria-label, 'Upload')]",
    ]

    # 先滾動頁面以顯示更多選項
    driver.execute_script("window.scrollBy(0, 500)")
    time.sleep(0.5)

    for selector in selectors:
        try:
            by = By.XPATH if selector.startswith("//") else By.CSS_SELECTOR
            element = WebDriverWait(driver, 5).until(
                EC.element_to_be_clickable((by, selector))
            )
            element.click()
            logger.info("已選擇「上傳檔案」")
            return True
        except TimeoutException:
            continue

    logger.error("找不到「上傳檔案」按鈕")
    _save_debug_screenshot(driver, "select_upload_source")
    return False


def _select_apple_music(driver: webdriver.Chrome) -> bool:
    """選擇 Apple Music 作為目標。

    目標平台選擇出現在流程的最後一步（STEP 4/4），
    按鈕 name/title 屬性與首頁相同。
    """
    selectors = [
        "button[name='Apple']",
        "button[title='Apple Music']",
        "button[aria-label='Apple Music']",
        "//button[@name='Apple']",
        "//button[@title='Apple Music']",
        "//*[contains(@title, 'Apple Music') and (self::button or self::div or self::a)]",
    ]

    # 等待目標選擇頁面載入（可能需要時間渲染）
    time.sleep(2)

    for selector in selectors:
        try:
            by = By.XPATH if selector.startswith("//") else By.CSS_SELECTOR
            element = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((by, selector))
            )
            element.click()
            logger.info("已選擇 Apple Music")
            return True
        except TimeoutException:
            continue

    logger.error("找不到 Apple Music 按鈕")
    _save_debug_screenshot(driver, "select_apple_music")
    return False


def _click_connect_button(driver: webdriver.Chrome) -> bool:
    """點擊「連接」按鈕。

    點擊後 TuneMyMusic 會：
    1. 按鈕文字變為 "Processing"
    2. 可能顯示 "Private mode isn't supported" 警告
    3. 開啟 Apple ID 登入彈窗 (idmsa.apple.com)
    """
    selectors = [
        "//*[normalize-space(text())='Connect']",
        "//*[normalize-space(text())='Sign in']",
        "//*[contains(text(), 'Connect') and not(contains(text(), 'Processing'))]",
        "//*[contains(text(), '連接')]",
        "//*[contains(text(), 'Sign in')]",
    ]

    for selector in selectors:
        try:
            by = By.XPATH if selector.startswith("//") else By.CSS_SELECTOR
            element = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((by, selector))
            )
            element.click()
            logger.info("已點擊「連接」按鈕")
            return True
        except TimeoutException:
            continue

    return False


def _wait_for_popup_auth(driver: webdriver.Chrome, main_window: str) -> bool:
    """等待 Apple ID 彈窗出現、使用者登入、彈窗關閉。

    Apple Music 授權流程：
    1. 點擊 Connect 後，TuneMyMusic 透過 MusicKit JS 發起 OAuth
    2. 瀏覽器開啟新視窗至 idmsa.apple.com 供使用者登入
    3. 使用者完成登入後彈窗自動關閉
    4. 主頁面收到授權 token，進入轉移步驟

    若未出現彈窗（可能已有快取的 session），直接返回 True。
    """
    print("\n" + "=" * 60)
    print("  請在彈出的視窗中登入 Apple ID")
    print("  完成授權後，此程式將自動繼續")
    print("=" * 60 + "\n")

    # 1. 等待 popup 視窗出現（最多 30 秒）
    popup_handle = None
    for _ in range(WAIT_TIMEOUT):
        handles = driver.window_handles
        new_handles = [h for h in handles if h != main_window]
        if new_handles:
            popup_handle = new_handles[0]
            logger.info(f"偵測到 Apple ID 彈窗（共 {len(handles)} 個視窗）")
            break
        time.sleep(1)

    if popup_handle is None:
        # 沒有彈窗出現 — 可能已有快取的授權 session
        logger.info("未偵測到彈窗，可能已有快取的授權 session")
        return True

    # 2. 切換至彈窗以記錄狀態（供除錯用）
    try:
        driver.switch_to.window(popup_handle)
        popup_url = driver.current_url
        logger.info(f"Apple ID 彈窗 URL：{popup_url}")
    except Exception as e:
        logger.warning(f"無法切換至彈窗：{e}")
    finally:
        # 切回主視窗
        driver.switch_to.window(main_window)

    # 3. 等待彈窗關閉（使用者完成登入）
    start_time = time.time()
    while time.time() - start_time < AUTH_TIMEOUT:
        handles = driver.window_handles
        if popup_handle not in handles:
            logger.info("Apple ID 彈窗已關閉（使用者完成登入）")
            # 確保回到主視窗
            driver.switch_to.window(main_window)
            return True

        elapsed = int(time.time() - start_time)
        if elapsed > 0 and elapsed % 30 == 0:
            logger.info(f"仍在等待使用者完成 Apple ID 登入... ({elapsed}s)")

        time.sleep(2)

    logger.error("等待 Apple ID 登入逾時")
    # 確保回到主視窗
    try:
        driver.switch_to.window(main_window)
    except Exception:
        pass
    return False


def _wait_for_auth_completion(driver: webdriver.Chrome) -> bool:
    """等待 Apple Music 授權完成：處理彈窗 + 確認主頁面進入轉移步驟。

    完整流程：
    1. 記錄主視窗 handle
    2. 等待 Apple ID 彈窗出現並由使用者完成登入
    3. 彈窗關閉後，確認主頁面已進入轉移步驟（出現 "Start Transfer" 按鈕）
    """
    main_window = driver.current_window_handle
    logger.info(f"主視窗 handle：{main_window}")

    # 等待彈窗授權流程完成
    if not _wait_for_popup_auth(driver, main_window):
        return False

    # 彈窗關閉後，等待主頁面更新至轉移步驟
    # 使用嚴格的 success indicators（避免 false positive）
    logger.info("等待主頁面進入轉移步驟...")
    time.sleep(3)  # 給頁面一點時間反應 OAuth callback

    # 嚴格指標：必須是 button 元素且文字精確匹配「Start Transfer」
    # 避免匹配頁面其他包含 "Start" 或 "Complete" 的無關元素
    strict_indicators = [
        "//button[normalize-space(text())='Start Transfer']",
        "//button[normalize-space(text())='Start transfer']",
        "//button[contains(normalize-space(text()), 'Start Transfer')]",
        "//button[contains(normalize-space(text()), 'Start transfer')]",
        "//button[normalize-space(text())='開始轉移']",
        # stickyButton 在轉移步驟可能被重用
        "//button[@name='stickyButton' and contains(text(), 'Start')]",
        "//button[@name='stickyButton' and contains(text(), '開始')]",
    ]

    start_time = time.time()
    post_auth_timeout = 60  # 彈窗關閉後最多等 60 秒頁面更新
    while time.time() - start_time < post_auth_timeout:
        for selector in strict_indicators:
            try:
                element = driver.find_element(By.XPATH, selector)
                btn_text = element.text.strip() if element.text else "(no text)"
                logger.info(f"授權完成！偵測到轉移按鈕：{btn_text}")
                return True
            except NoSuchElementException:
                continue

        # 額外檢查：是否出現 progress bar 或 track count（代表已進入轉移頁面）
        try:
            driver.find_element(
                By.XPATH,
                "//*[contains(@class, 'progress') or contains(@class, 'Progress')]"
                "[ancestor::*[contains(@class, 'transfer') or contains(@class, 'Transfer')]]",
            )
            logger.info("授權完成！偵測到轉移進度元素")
            return True
        except NoSuchElementException:
            pass

        time.sleep(2)

    # 記錄頁面狀態以便除錯
    try:
        page_text = driver.execute_script(
            "return document.body ? document.body.innerText.substring(0, 1000) : ''"
        )
        logger.warning(f"授權後未偵測到轉移步驟，頁面內容片段：{page_text[:500]}")
    except Exception:
        pass

    logger.error("授權完成但未能進入轉移步驟")
    return False


def _start_transfer(driver: webdriver.Chrome) -> bool:
    """開始轉移。

    使用嚴格的 selector：必須是 button 元素且文字包含 "Start Transfer"。
    避免匹配頁面上其他包含 "Start" 的無關元素。
    """
    selectors = [
        # 嚴格：僅匹配 button 元素
        "//button[contains(normalize-space(text()), 'Start Transfer')]",
        "//button[contains(normalize-space(text()), 'Start transfer')]",
        "//button[normalize-space(text())='開始轉移']",
        # stickyButton 可能被重用
        "//button[@name='stickyButton' and contains(text(), 'Start')]",
        "//button[@name='stickyButton' and contains(text(), '開始')]",
    ]

    for selector in selectors:
        try:
            by = By.XPATH if selector.startswith("//") else By.CSS_SELECTOR
            element = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((by, selector))
            )
            btn_text = element.text.strip() if element.text else "(no text)"
            element.click()
            logger.info(f"已開始轉移（按鈕文字：{btn_text}）")
            return True
        except TimeoutException:
            continue

    return False


def _wait_for_transfer_completion(driver: webdriver.Chrome) -> bool:
    """等待轉移完成。

    使用嚴格的完成指標：
    - 避免匹配頁面上其他包含 "Complete" 或 "Done" 的無關元素
    - 優先偵測 TuneMyMusic 特有的完成文字（如 "X tracks transferred"）
    - 監控進度變化以偵測轉移是否實際在進行
    """
    print("\n  正在轉移曲目至 Apple Music...")

    # TuneMyMusic 完成頁面的嚴格指標
    # 轉移完成時會顯示類似 "123 tracks transferred" 或 "Completed" 的訊息
    completion_indicators = [
        # 包含具體數字的完成訊息（最可靠）
        "//*[contains(text(), 'tracks transferred')]",
        "//*[contains(text(), 'songs transferred')]",
        "//*[contains(text(), '首曲目已轉移')]",
        "//*[contains(text(), '已轉移')]",
        # TuneMyMusic 特有的完成狀態
        "//*[contains(text(), 'Transfer Complete')]",
        "//*[contains(text(), 'Transfer complete')]",
        "//*[contains(text(), '轉移完成')]",
        # "Done" 按鈕（僅匹配 button 避免 false positive）
        "//button[normalize-space(text())='Done']",
        "//button[normalize-space(text())='完成']",
        # 出現 "Move to" 或 "Share" 選項代表轉移結束
        "//*[contains(text(), 'Move to another')]",
        "//*[contains(text(), 'Share')]",
    ]

    # 失敗指標
    failure_indicators = [
        "//*[contains(text(), 'Transfer Failed')]",
        "//*[contains(text(), 'Transfer failed')]",
        "//*[contains(text(), 'Error')]",
        "//*[contains(text(), '轉移失敗')]",
    ]

    start_time = time.time()
    last_log_time = start_time
    while time.time() - start_time < AUTH_TIMEOUT:
        # 檢查完成指標
        for selector in completion_indicators:
            try:
                element = driver.find_element(By.XPATH, selector)
                text = element.text.strip() if element.text else "(no text)"
                logger.info(f"轉移完成！偵測到：{text}")
                return True
            except NoSuchElementException:
                continue

        # 檢查失敗指標
        for selector in failure_indicators:
            try:
                element = driver.find_element(By.XPATH, selector)
                text = element.text.strip() if element.text else "(no text)"
                logger.error(f"轉移失敗：{text}")
                return False
            except NoSuchElementException:
                continue

        # 每 30 秒記錄一次進度
        elapsed = time.time() - start_time
        if elapsed - (last_log_time - start_time) >= 30:
            last_log_time = time.time()
            try:
                # 嘗試讀取進度百分比或已轉移數量
                progress_text = driver.execute_script("""
                    var texts = [];
                    var elements = document.querySelectorAll('[class*="progress"], [class*="Progress"], [class*="percent"], [class*="count"]');
                    elements.forEach(function(el) { if (el.textContent.trim()) texts.push(el.textContent.trim()); });
                    return texts.join(' | ');
                """)
                if progress_text:
                    logger.info(f"轉移進行中 ({int(elapsed)}s)：{progress_text[:200]}")
                else:
                    logger.info(f"轉移進行中 ({int(elapsed)}s)...")
            except Exception:
                logger.info(f"轉移進行中 ({int(elapsed)}s)...")

        time.sleep(3)

    logger.error("轉移逾時")
    return False


def import_to_apple_music(
    csv_path: str,
    keep_browser_open: bool = False,
    playlist_name: str | None = None,
) -> bool:
    """將 CSV 檔案透過 TuneMyMusic 匯入 Apple Music。

    Args:
        csv_path: CSV 檔案的絕對路徑
        keep_browser_open: 完成後是否保持瀏覽器開啟（預設自動關閉）
        playlist_name: 目標播放清單名稱（若不指定則使用 CSV 檔名）

    Returns:
        是否成功
    """
    csv_path = str(Path(csv_path).resolve())

    if not Path(csv_path).exists():
        logger.error(f"CSV 檔案不存在：{csv_path}")
        return False

    print("\n  正在啟動瀏覽器...")
    driver = _create_driver()

    try:
        # 1. 開啟 TuneMyMusic
        logger.info(f"正在開啟 {TUNEMYMUSIC_URL}")
        driver.get(TUNEMYMUSIC_URL)
        time.sleep(2)

        # 1.5 關閉 cookie 同意彈窗（若存在）
        _dismiss_cookie_consent(driver)
        time.sleep(1)

        # 2. 選擇「上傳檔案」作為來源
        if not _select_upload_source(driver):
            return False
        time.sleep(3)  # 等待 SPA 導航至 /transfer 頁面

        # 3. 上傳 CSV 檔案
        if not _upload_file(driver, csv_path):
            return False
        time.sleep(10)  # 等待檔案處理與 React 渲染欄位對應 UI

        # 4. 點擊「繼續」通過中間步驟
        #    新版 TuneMyMusic 有 4 個步驟（URL 皆為 /transfer）：
        #    Step 1: 選擇來源 → Step 2: 上傳/對應欄位 + 選擇歌單 → Step 3: 選擇目標
        #    Step 2 有兩個子步驟（field mapping → playlist selection），
        #    共用 stickyButton，按鈕文字分別為 "Continue" 和 "Choose Destination"。
        #    需等待 React 載入大量曲目清單（178 首需約 10 秒）。
        for step in range(5):
            if _click_continue_button(driver):
                logger.info(f"已通過中間步驟（第 {step + 1} 次）")
                time.sleep(10)  # 等待 React 重新渲染下一步驟
            else:
                break

        # 4.5 設定播放清單名稱（在選擇目標之前）
        if playlist_name:
            _set_playlist_name(driver, playlist_name)
            time.sleep(1)

        # 5. 選擇 Apple Music 作為目標
        if not _select_apple_music(driver):
            return False
        time.sleep(2)

        # 6. 點擊「連接」並等待 Apple ID 授權
        #    Connect 點擊後會觸發 MusicKit JS OAuth：
        #    - 可能開啟 Apple ID 登入彈窗（使用者需手動登入）
        #    - 若有快取 session 則可能直接進入轉移步驟
        if not _click_connect_button(driver):
            logger.warning("未找到 Connect 按鈕，嘗試繼續流程...")
        time.sleep(3)  # 等待 OAuth 初始化

        # 7. 等待授權完成（處理彈窗 + 確認進入轉移步驟）
        if not _wait_for_auth_completion(driver):
            return False

        # 7.5 刪除同名的現有 Apple Music 播放清單（避免重複）
        if playlist_name:
            _delete_existing_apple_music_playlist(driver, playlist_name)
            time.sleep(2)

        # 8. 開始轉移（auth completion 已確認 Start Transfer 按鈕存在）
        if not _start_transfer(driver):
            logger.warning("未找到 Start Transfer 按鈕，轉移可能已自動開始")

        # 9. 等待轉移完成
        if _wait_for_transfer_completion(driver):
            print("\n  匯入完成！請至 Apple Music 確認播放清單。")
            logger.info("匯入成功")
        else:
            print("\n  轉移可能仍在進行中，請在瀏覽器中確認。")

        # 完成後等待 3 秒讓使用者看到結果
        time.sleep(3)

        return True

    except Exception as e:
        logger.error(f"匯入失敗：{e}")
        return False

    finally:
        if not keep_browser_open:
            driver.quit()
            logger.info("瀏覽器已關閉")
