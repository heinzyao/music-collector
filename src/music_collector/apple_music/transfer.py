"""TuneMyMusic UI 自動化：上傳 CSV、選擇目標、執行轉移。"""

import csv
import logging
import time
from pathlib import Path

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from selenium.common.exceptions import TimeoutException, NoSuchElementException

from .browser import (
    TUNEMYMUSIC_URL,
    WAIT_TIMEOUT,
    AUTH_TIMEOUT,
    create_driver,
    dismiss_cookie_consent,
    save_debug_screenshot,
)
from .playlist import (
    delete_existing_playlist,
    rename_playlist,
    deduplicate_playlists,
)

# TuneMyMusic 免費方案每次轉移上限
MAX_TRACKS_PER_TRANSFER = 500


def _split_csv(csv_path: str, max_tracks: int = MAX_TRACKS_PER_TRANSFER) -> list[str]:
    """將超過 max_tracks 的 CSV 分割為多個批次檔案。

    若曲目數未超過上限，直接回傳原始路徑。
    分割檔案命名為 {原名}_batch1.csv、_batch2.csv …，結束後由呼叫端清理。
    """
    src = Path(csv_path)
    with src.open(encoding="utf-8") as f:
        reader = csv.reader(f)
        header = next(reader)
        rows = list(reader)

    if len(rows) <= max_tracks:
        return [csv_path]

    batch_paths: list[str] = []
    for i in range(0, len(rows), max_tracks):
        batch_num = i // max_tracks + 1
        batch_path = src.with_name(f"{src.stem}_batch{batch_num}{src.suffix}")
        with batch_path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(header)
            writer.writerows(rows[i : i + max_tracks])
        batch_paths.append(str(batch_path))
        logger.info(
            f"批次 {batch_num}：{len(rows[i : i + max_tracks])} 首（共 {len(rows)} 首）"
        )

    return batch_paths


logger = logging.getLogger(__name__)


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

        # react-dropzone 使用 clip-path: inset(50%) 隱藏 input，
        # 需同時清除 clip/clip-path 才能讓 Selenium 4 的互動檢查通過
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
            "el.style.clip = 'auto';"
            "el.style.clipPath = 'none';"
            "el.style.overflow = 'visible';"
            "el.style.whiteSpace = 'normal';"
            "el.removeAttribute('hidden');"
            "el.removeAttribute('aria-hidden');"
            "el.removeAttribute('tabindex');"
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
        save_debug_screenshot(driver, "upload_file")
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
        "//button[normalize-space(text())='Continue']",
        "//button[normalize-space(text())='Choose Destination']",
        "//button[normalize-space(text())='繼續']",
        "//button[normalize-space(text())='選擇目的地']",
        "//button[contains(text(), 'Next')]",
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
        result = driver.execute_script(
            """
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
        """,
            name,
        )

        if result:
            logger.info(f"已透過 JS 設定播放清單名稱為：{name}（元素：{result}）")
            return
    except Exception as e:
        logger.debug(f"JS 搜尋播放清單名稱欄位失敗：{e}")

    logger.warning(f"找不到播放清單名稱編輯欄位，將使用 CSV 檔名作為播放清單名稱")
    save_debug_screenshot(driver, "set_playlist_name")


def _select_upload_source(driver: webdriver.Chrome) -> bool:
    """選擇「上傳檔案」作為來源。

    TuneMyMusic SPA 的 Step 1 顯示來源選擇磁貼，
    button[name='FromFile'] 是最穩定的 selector（不受語系影響）。

    注意：cookie consent overlay 可能攔截點擊，
    需使用 JS click 作為後備以繞過 ElementClickInterceptedException。
    """
    # 等待 React SPA 實際渲染來源選擇按鈕
    logger.info("等待來源選擇頁面載入...")
    try:
        WebDriverWait(driver, WAIT_TIMEOUT).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "button[name='FromFile']"))
        )
        logger.info("來源選擇頁面已就緒")
    except TimeoutException:
        logger.warning("等待 button[name='FromFile'] 逾時，仍嘗試後備方式")

    driver.execute_script("window.scrollTo(0, 0)")
    time.sleep(0.5)

    # 優先使用 name attribute（最穩定），先嘗試原生點擊再用 JS 點擊
    css_selectors = [
        "button[name='FromFile']",
        "button[title='Upload file']",
        "button[title='上傳文件']",
        "button[aria-label='Upload file']",
        "button[aria-label='上傳文件']",
    ]
    xpath_selectors = [
        "//button[contains(@title, 'Upload')]",
        "//button[contains(@title, '上傳')]",
        "//button[contains(@aria-label, 'Upload')]",
        "//button[contains(@aria-label, '上傳')]",
    ]

    # 第一輪：原生 Selenium 點擊
    for selector in css_selectors + xpath_selectors:
        try:
            by = By.XPATH if selector.startswith("//") else By.CSS_SELECTOR
            element = WebDriverWait(driver, 5).until(
                EC.element_to_be_clickable((by, selector))
            )
            element.click()
            logger.info(f"已選擇「上傳檔案」（selector: {selector}）")
            return True
        except TimeoutException:
            continue
        except Exception:
            # ElementClickInterceptedException 等——改用 JS 點擊
            continue

    # 第二輪：JS 點擊（繞過 overlay 攔截）
    for selector in css_selectors:
        try:
            clicked = driver.execute_script(
                "var el = document.querySelector(arguments[0]);"
                "if (el) { el.click(); return true; }"
                "return false;",
                selector,
            )
            if clicked:
                logger.info(f"已透過 JS 選擇「上傳檔案」（selector: {selector}）")
                return True
        except Exception:
            continue

    logger.error(f"找不到「上傳檔案」按鈕，當前 URL: {driver.current_url}")
    save_debug_screenshot(driver, "select_upload_source")
    return False


def _select_apple_music(driver: webdriver.Chrome) -> bool:
    """選擇 Apple Music 作為目標。"""
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
    save_debug_screenshot(driver, "select_apple_music")
    return False


def _click_connect_button(driver: webdriver.Chrome) -> bool:
    """點擊「連接」按鈕。"""
    selectors = [
        "//button[normalize-space(text())='Connect']",
        "//button[normalize-space(text())='Sign in']",
        "//button[contains(text(), 'Connect') and not(contains(text(), 'Processing'))]",
        "//button[contains(text(), '連接')]",
        "//button[contains(text(), 'Sign in')]",
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
    """等待 Apple ID 彈窗出現、使用者登入、彈窗關閉。"""
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
        logger.info("未偵測到彈窗，可能已有快取的授權 session")
        try:
            music_token = driver.execute_script(
                "try { return localStorage.getItem('music.ampwebplay.token') "
                "|| localStorage.getItem('mk-token') "
                "|| document.cookie.includes('media-user-token') "
                "? 'present' : 'absent'; } catch(e) { return 'error: ' + e.message; }"
            )
            logger.info(f"Apple Music auth token 狀態：{music_token}")
            if music_token and "absent" in str(music_token):
                logger.warning("未偵測到 Apple Music token，快取授權可能已失效")
        except Exception as e:
            logger.warning(f"無法檢查 auth token 狀態：{e}")
        return True

    # 2. 切換至彈窗以記錄狀態（供除錯用）
    try:
        driver.switch_to.window(popup_handle)
        popup_url = driver.current_url
        logger.info(f"Apple ID 彈窗 URL：{popup_url}")
    except Exception as e:
        logger.warning(f"無法切換至彈窗：{e}")
    finally:
        driver.switch_to.window(main_window)

    # 3. 等待彈窗關閉（使用者完成登入）
    start_time = time.time()
    while time.time() - start_time < AUTH_TIMEOUT:
        handles = driver.window_handles
        if popup_handle not in handles:
            logger.info("Apple ID 彈窗已關閉（使用者完成登入）")
            driver.switch_to.window(main_window)
            return True

        elapsed = int(time.time() - start_time)
        if elapsed > 0 and elapsed % 30 == 0:
            logger.info(f"仍在等待使用者完成 Apple ID 登入... ({elapsed}s)")

        time.sleep(2)

    logger.error("等待 Apple ID 登入逾時")
    try:
        driver.switch_to.window(main_window)
    except Exception:
        pass
    return False


def _wait_for_auth_completion(driver: webdriver.Chrome) -> bool:
    """等待 Apple Music 授權完成：處理彈窗 + 確認主頁面進入轉移步驟。"""
    main_window = driver.current_window_handle
    logger.info(f"主視窗 handle：{main_window}")

    if not _wait_for_popup_auth(driver, main_window):
        return False

    logger.info("等待主頁面進入轉移步驟...")
    time.sleep(3)

    strict_indicators = [
        "//button[normalize-space(text())='Start Transfer']",
        "//button[normalize-space(text())='Start transfer']",
        # 排除 Premium 付費牆按鈕（如 "Go Premium And Start Transfer"）
        "//button[contains(normalize-space(text()), 'Start Transfer') and not(contains(text(), 'Premium'))]",
        "//button[contains(normalize-space(text()), 'Start transfer') and not(contains(text(), 'Premium'))]",
        "//button[normalize-space(text())='開始轉移']",
        "//button[@name='stickyButton' and contains(text(), 'Start') and not(contains(text(), 'Premium'))]",
        "//button[@name='stickyButton' and contains(text(), '開始')]",
    ]

    start_time = time.time()
    post_auth_timeout = 60
    while time.time() - start_time < post_auth_timeout:
        # 先檢查是否出現 Premium 付費牆
        try:
            premium_btn = driver.find_element(
                By.XPATH,
                "//button[contains(text(), 'Premium') and contains(text(), 'Transfer')]",
            )
            btn_text = premium_btn.text.strip() if premium_btn.text else ""
            logger.error(
                f"TuneMyMusic 需要 Premium 方案才能轉移至 Apple Music（按鈕：{btn_text}）"
            )
            return False
        except NoSuchElementException:
            pass

        for selector in strict_indicators:
            try:
                element = driver.find_element(By.XPATH, selector)
                btn_text = element.text.strip() if element.text else "(no text)"
                logger.info(f"授權完成！偵測到轉移按鈕：{btn_text}")
                return True
            except NoSuchElementException:
                continue

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
    """開始轉移。"""
    selectors = [
        # 排除 Premium 付費牆按鈕（如 "Go Premium And Start Transfer"）
        "//button[contains(normalize-space(text()), 'Start Transfer') and not(contains(text(), 'Premium'))]",
        "//button[contains(normalize-space(text()), 'Start transfer') and not(contains(text(), 'Premium'))]",
        "//button[normalize-space(text())='開始轉移']",
        "//button[@name='stickyButton' and contains(text(), 'Start') and not(contains(text(), 'Premium'))]",
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

    注意：TuneMyMusic SPA 頁面中可能存在隱藏元素匹配 completion indicator，
    必須檢查元素是否可見（is_displayed()）且包含有效文字，避免 false positive。
    另外需等待一段起始延遲，確保 Start Transfer 按鈕點擊後頁面已開始轉移。
    """
    print("\n  正在轉移曲目至 Apple Music...")

    completion_indicators = [
        "//*[contains(text(), 'tracks transferred')]",
        "//*[contains(text(), 'songs transferred')]",
        "//*[contains(text(), '首曲目已轉移')]",
        "//*[contains(text(), '已轉移')]",
        "//*[contains(text(), 'Transfer Complete')]",
        "//*[contains(text(), 'Transfer complete')]",
        "//*[contains(text(), '轉移完成')]",
        "//button[normalize-space(text())='Done']",
        "//button[normalize-space(text())='完成']",
        "//button[contains(text(), 'Move to another')]",
        "//button[normalize-space(text())='Share']",
    ]

    failure_indicators = [
        "//*[contains(text(), 'Transfer Failed')]",
        "//*[contains(text(), 'Transfer failed')]",
        "//*[contains(text(), 'Transfer error')]",
        "//*[contains(text(), '轉移失敗')]",
    ]

    # 起始延遲：等待頁面從「Start Transfer」狀態過渡到轉移中狀態，
    # 避免匹配到轉移開始前頁面上的隱藏/殘留元素導致 false positive。
    logger.info("等待轉移啟動（10 秒起始延遲）...")
    time.sleep(10)

    start_time = time.time()
    last_log_time = start_time
    while time.time() - start_time < AUTH_TIMEOUT:
        for selector in completion_indicators:
            try:
                elements = driver.find_elements(By.XPATH, selector)
                for element in elements:
                    # 必須檢查元素可見且包含有效文字，避免匹配隱藏元素
                    if not element.is_displayed():
                        continue
                    text = element.text.strip() if element.text else ""
                    if not text:
                        continue
                    logger.info(f"轉移完成！偵測到：{text}")
                    return True
            except NoSuchElementException:
                continue

        for selector in failure_indicators:
            try:
                elements = driver.find_elements(By.XPATH, selector)
                for element in elements:
                    if not element.is_displayed():
                        continue
                    text = element.text.strip() if element.text else ""
                    if not text:
                        continue
                    logger.error(f"轉移失敗：{text}")
                    return False
            except NoSuchElementException:
                continue

        elapsed = time.time() - start_time
        if elapsed - (last_log_time - start_time) >= 30:
            last_log_time = time.time()
            try:
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


def _run_transfer_batch(
    driver: webdriver.Chrome,
    batch_csv: str,
    playlist_name: str | None,
    is_first_batch: bool,
) -> bool:
    """執行單次 TuneMyMusic 轉移流程（導航 → 上傳 → 授權 → 轉移）。

    is_first_batch 為 True 時會嘗試連接 Apple ID 並刪除同名現有歌單；
    後續批次跳過這些步驟，直接利用快取的授權。
    """
    logger.info(f"正在開啟 {TUNEMYMUSIC_URL}")
    driver.get(TUNEMYMUSIC_URL)
    time.sleep(2)

    if "/transfer" not in driver.current_url:
        logger.info("導航至轉移入口頁面...")
        driver.get(f"{TUNEMYMUSIC_URL}transfer")
        try:
            WebDriverWait(driver, 10).until(lambda d: "/transfer" in d.current_url)
            logger.info(f"已導航至 {driver.current_url}")
        except TimeoutException:
            logger.warning("等待 /transfer 重導向逾時，繼續嘗試")

    dismiss_cookie_consent(driver)
    time.sleep(1)

    if not _select_upload_source(driver):
        return False
    time.sleep(5)

    if not _upload_file(driver, batch_csv):
        return False
    time.sleep(10)

    for step in range(5):
        if _click_continue_button(driver):
            logger.info(f"已通過中間步驟（第 {step + 1} 次）")
            time.sleep(10)
        else:
            break

    if playlist_name:
        _set_playlist_name(driver, playlist_name)
        time.sleep(1)

    if not _select_apple_music(driver):
        return False
    time.sleep(2)

    if is_first_batch:
        if not _click_connect_button(driver):
            logger.warning("未找到 Connect 按鈕，嘗試繼續流程...")
        time.sleep(3)

    if not _wait_for_auth_completion(driver):
        return False

    if is_first_batch and playlist_name:
        delete_existing_playlist(driver, playlist_name)
        time.sleep(2)

    if not _start_transfer(driver):
        logger.warning("未找到 Start Transfer 按鈕，轉移可能已自動開始")

    return _wait_for_transfer_completion(driver)


def import_to_apple_music(
    csv_path: str,
    keep_browser_open: bool = False,
    playlist_name: str | None = None,
) -> bool:
    """將 CSV 檔案透過 TuneMyMusic 匯入 Apple Music。

    若 CSV 超過 500 首（TuneMyMusic 免費上限），自動分批傳輸。

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

    batch_paths = _split_csv(csv_path)
    total_batches = len(batch_paths)
    if total_batches > 1:
        logger.info(
            f"CSV 超過 {MAX_TRACKS_PER_TRANSFER} 首，分為 {total_batches} 批次傳輸"
        )

    print("\n  正在啟動瀏覽器...")
    driver = create_driver()

    try:
        all_ok = True
        for batch_idx, batch_csv in enumerate(batch_paths):
            is_first = batch_idx == 0
            batch_label = (
                f"[{batch_idx + 1}/{total_batches}] " if total_batches > 1 else ""
            )

            logger.info(f"{batch_label}開始傳輸批次")
            batch_ok = _run_transfer_batch(driver, batch_csv, playlist_name, is_first)

            if batch_ok:
                logger.info(f"{batch_label}匯入完成")
            else:
                logger.warning(f"{batch_label}轉移未確認完成")
                all_ok = False
                break

            if batch_idx < total_batches - 1:
                logger.info(f"{batch_label}等待後繼續下一批次...")
                time.sleep(5)

        if all_ok:
            print("\n  匯入完成！請至 Apple Music 確認播放清單。")
            logger.info("全部批次匯入成功")
        else:
            print("\n  轉移可能仍在進行中或失敗，請在瀏覽器中確認。")
            logger.warning("轉移未確認完成，跳過後續改名與去重步驟")

        if all_ok and playlist_name:
            time.sleep(2)
            rename_playlist(driver, playlist_name, csv_path)

        if all_ok and playlist_name:
            time.sleep(2)
            deduplicate_playlists(driver, playlist_name)

        time.sleep(3)

        return all_ok

    except Exception as e:
        logger.error(f"匯入失敗：{e}")
        return False

    finally:
        for p in batch_paths:
            if p != csv_path:
                try:
                    Path(p).unlink()
                except OSError:
                    pass
        if not keep_browser_open:
            driver.quit()
            logger.info("瀏覽器已關閉")
