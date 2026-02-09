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


def _create_driver() -> webdriver.Chrome:
    """建立 Chrome WebDriver。"""
    options = Options()
    # 不使用 headless 模式，因為需要使用者手動授權
    options.add_argument("--start-maximized")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)

    driver = webdriver.Chrome(options=options)
    # 隱藏 webdriver 特徵
    driver.execute_script(
        "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
    )
    return driver


def _wait_and_click(driver: webdriver.Chrome, selector: str, by: By = By.CSS_SELECTOR, timeout: int = WAIT_TIMEOUT) -> bool:
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


def _wait_for_element(driver: webdriver.Chrome, selector: str, by: By = By.CSS_SELECTOR, timeout: int = WAIT_TIMEOUT):
    """等待元素出現。"""
    try:
        return WebDriverWait(driver, timeout).until(
            EC.presence_of_element_located((by, selector))
        )
    except TimeoutException:
        return None


def _upload_file(driver: webdriver.Chrome, csv_path: str) -> bool:
    """上傳 CSV 檔案。"""
    try:
        # 等待隱藏的 file input 出現
        file_input = WebDriverWait(driver, WAIT_TIMEOUT).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "input[type='file']"))
        )
        # 直接送入檔案路徑
        file_input.send_keys(csv_path)
        logger.info(f"已上傳檔案：{csv_path}")
        return True
    except TimeoutException:
        logger.error("找不到檔案上傳欄位")
        return False


def _click_continue_button(driver: webdriver.Chrome) -> bool:
    """點擊繼續/確認按鈕。"""
    # 嘗試多種可能的選擇器
    selectors = [
        "button[class*='startTransferBtn']",
        "button[class*='StickyButton']",
        "//button[contains(text(), '繼續')]",
        "//button[contains(text(), 'Continue')]",
        "//button[contains(text(), '選擇目的地')]",
        "//button[contains(text(), 'Select Destination')]",
    ]

    for selector in selectors:
        try:
            by = By.XPATH if selector.startswith("//") else By.CSS_SELECTOR
            element = WebDriverWait(driver, 5).until(
                EC.element_to_be_clickable((by, selector))
            )
            element.click()
            time.sleep(1)  # 等待頁面轉換
            return True
        except TimeoutException:
            continue

    return False


def _select_upload_source(driver: webdriver.Chrome) -> bool:
    """選擇「上傳檔案」作為來源。"""
    selectors = [
        "button[title='上傳文件']",
        "button[title='Upload File']",
        "//button[contains(@title, 'Upload')]",
        "//button[contains(@title, '上傳')]",
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
    return False


def _select_apple_music(driver: webdriver.Chrome) -> bool:
    """選擇 Apple Music 作為目標。"""
    selectors = [
        "button[title='Apple Music']",
        "//button[@title='Apple Music']",
    ]

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
    return False


def _click_connect_button(driver: webdriver.Chrome) -> bool:
    """點擊「連接」按鈕。"""
    selectors = [
        "button.ColorTMMButton",
        "//button[contains(text(), '連接')]",
        "//button[contains(text(), 'Connect')]",
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


def _wait_for_auth_completion(driver: webdriver.Chrome) -> bool:
    """等待 Apple Music 授權完成。"""
    print("\n" + "=" * 60)
    print("🍎 請在彈出的視窗中登入 Apple ID")
    print("   完成授權後，此程式將自動繼續")
    print("=" * 60 + "\n")

    # 等待授權完成（頁面會顯示成功訊息或進入下一步）
    success_indicators = [
        "//div[contains(text(), '成功')]",
        "//div[contains(text(), 'Success')]",
        "//button[contains(text(), '開始轉移')]",
        "//button[contains(text(), 'Start Transfer')]",
        "button[class*='startTransferBtn']",
    ]

    start_time = time.time()
    while time.time() - start_time < AUTH_TIMEOUT:
        for selector in success_indicators:
            try:
                by = By.XPATH if selector.startswith("//") else By.CSS_SELECTOR
                driver.find_element(by, selector)
                logger.info("授權完成！")
                return True
            except NoSuchElementException:
                continue
        time.sleep(2)

    logger.error("授權逾時")
    return False


def _start_transfer(driver: webdriver.Chrome) -> bool:
    """開始轉移。"""
    selectors = [
        "//button[contains(text(), '開始轉移')]",
        "//button[contains(text(), 'Start Transfer')]",
        "button[class*='startTransferBtn']",
    ]

    for selector in selectors:
        try:
            by = By.XPATH if selector.startswith("//") else By.CSS_SELECTOR
            element = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((by, selector))
            )
            element.click()
            logger.info("已開始轉移")
            return True
        except TimeoutException:
            continue

    return False


def _wait_for_transfer_completion(driver: webdriver.Chrome) -> bool:
    """等待轉移完成。"""
    print("\n⏳ 正在轉移曲目至 Apple Music...")

    completion_indicators = [
        "//div[contains(text(), '完成')]",
        "//div[contains(text(), 'Complete')]",
        "//div[contains(text(), '已轉移')]",
        "//div[contains(text(), 'transferred')]",
    ]

    start_time = time.time()
    while time.time() - start_time < AUTH_TIMEOUT:
        for selector in completion_indicators:
            try:
                driver.find_element(By.XPATH, selector)
                return True
            except NoSuchElementException:
                continue
        time.sleep(3)

    return False


def import_to_apple_music(csv_path: str, keep_browser_open: bool = False) -> bool:
    """將 CSV 檔案透過 TuneMyMusic 匯入 Apple Music。

    Args:
        csv_path: CSV 檔案的絕對路徑
        keep_browser_open: 完成後是否保持瀏覽器開啟（預設自動關閉）

    Returns:
        是否成功
    """
    csv_path = str(Path(csv_path).resolve())

    if not Path(csv_path).exists():
        logger.error(f"CSV 檔案不存在：{csv_path}")
        return False

    print("\n🚀 正在啟動瀏覽器...")
    driver = _create_driver()

    try:
        # 1. 開啟 TuneMyMusic
        logger.info(f"正在開啟 {TUNEMYMUSIC_URL}")
        driver.get(TUNEMYMUSIC_URL)
        time.sleep(2)

        # 2. 選擇「上傳檔案」作為來源
        if not _select_upload_source(driver):
            return False
        time.sleep(1)

        # 3. 上傳 CSV 檔案
        if not _upload_file(driver, csv_path):
            return False
        time.sleep(2)

        # 4. 點擊「繼續」（可能需要多次）
        for _ in range(3):
            if _click_continue_button(driver):
                time.sleep(2)

        # 5. 選擇 Apple Music 作為目標
        if not _select_apple_music(driver):
            return False
        time.sleep(1)

        # 6. 點擊「連接」
        if not _click_connect_button(driver):
            # 可能直接進入授權流程
            pass
        time.sleep(2)

        # 7. 等待使用者完成 Apple Music 授權
        if not _wait_for_auth_completion(driver):
            return False

        # 8. 開始轉移
        _start_transfer(driver)

        # 9. 等待轉移完成
        if _wait_for_transfer_completion(driver):
            print("\n✅ 匯入完成！請至 Apple Music 確認播放清單。")
            logger.info("匯入成功")
        else:
            print("\n⚠️  轉移可能仍在進行中，請在瀏覽器中確認。")

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

