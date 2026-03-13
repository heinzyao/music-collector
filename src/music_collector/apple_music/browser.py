"""瀏覽器管理：Chrome WebDriver 建立、反偵測、工具函式。"""

import logging
import time
from datetime import datetime
from pathlib import Path

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
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

# Apple Music API 存取的共用 JavaScript 程式碼。
# 執行後可用的變數與函式：
#   canUseMusicKitApi (bool) — MusicKit JS 實例可用
#   canUseFetch (bool)       — 有 developer token + user token 可用 fetch
#   apiGet(path)             — GET 請求
#   apiPatch(path, body)     — PATCH 請求
#   apiDelete(path)          — DELETE 請求
#   _apiDebugInfo()          — 回傳診斷資訊物件
APPLE_MUSIC_API_JS = """
    // --- 取得 MusicKit 實例 ---
    var music = null;
    if (typeof MusicKit !== 'undefined') {
        try { music = MusicKit.getInstance(); } catch(e) {}
        if (!music) {
            try {
                var inst = MusicKit.instances;
                if (inst && inst.length > 0) music = inst[0];
            } catch(e) {}
        }
    }
    if (!music && window.music) music = window.music;

    var canUseMusicKitApi = !!(music && music.api &&
                               typeof music.api.music === 'function');

    // --- 若 MusicKit 未設定，嘗試用攔截器保存的 token 重新設定 ---
    var devToken = null;
    var userToken = null;

    if (!canUseMusicKitApi && typeof MusicKit !== 'undefined' && MusicKit.configure) {
        // 從攔截器保存的 localStorage 取得 developer token
        try { devToken = localStorage.getItem('__tmm_apple_dev_token'); } catch(e) {}

        // user token 的 key 格式為 music.{appId}.u
        if (devToken) {
            try {
                for (var i = 0; i < localStorage.length; i++) {
                    var key = localStorage.key(i);
                    if (/^music\\..+\\.u$/.test(key)) {
                        userToken = localStorage.getItem(key);
                        break;
                    }
                }
            } catch(e) {}

            // 若兩個 token 都有，嘗試設定 MusicKit 實例
            if (userToken) {
                try {
                    music = MusicKit.configure({
                        developerToken: devToken,
                        app: {
                            name: 'TuneMyMusic',
                            icon: 'https://www.tunemymusic.com/images/192_logo.png',
                            build: '1.0'
                        }
                    });
                    canUseMusicKitApi = !!(music && music.api &&
                                           typeof music.api.music === 'function');
                } catch(e) {}
            }
        }
    }

    // --- 提取 token 用於 fetch 備援 ---
    if (!canUseMusicKitApi) {
        // 從 MusicKit 實例取 token（實例可能存在但 .api 不可用）
        if (music) {
            if (!devToken) devToken = music.developerToken || null;
            if (!userToken) userToken = music.musicUserToken || null;
        }

        // 從 localStorage 搜尋（攔截器 + MusicKit 儲存格式）
        if (!devToken) {
            try { devToken = localStorage.getItem('__tmm_apple_dev_token'); } catch(e) {}
        }
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
    }

    var canUseFetch = !!(devToken && userToken);

    // --- 共用 API 呼叫函式 ---
    async function apiGet(path) {
        if (canUseMusicKitApi) {
            var r = await music.api.music(path);
            return r.data;
        }
        var r = await fetch('https://api.music.apple.com' + path, {
            headers: {
                'Authorization': 'Bearer ' + devToken,
                'Music-User-Token': userToken
            }
        });
        if (!r.ok) throw new Error('GET ' + path + ' failed: HTTP ' + r.status);
        return await r.json();
    }

    async function apiPatch(path, body) {
        if (canUseMusicKitApi) {
            await music.api.music(path, {}, {
                method: 'PATCH',
                body: JSON.stringify(body)
            });
            return;
        }
        var r = await fetch('https://api.music.apple.com' + path, {
            method: 'PATCH',
            headers: {
                'Authorization': 'Bearer ' + devToken,
                'Music-User-Token': userToken,
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(body)
        });
        if (!r.ok) throw new Error('PATCH ' + path + ' failed: HTTP ' + r.status);
    }

    async function apiDelete(path) {
        if (canUseMusicKitApi) {
            await music.api.music(path, {}, {method: 'DELETE'});
            return;
        }
        var r = await fetch('https://api.music.apple.com' + path, {
            method: 'DELETE',
            headers: {
                'Authorization': 'Bearer ' + devToken,
                'Music-User-Token': userToken
            }
        });
        if (!r.ok) throw new Error('DELETE ' + path + ' failed: HTTP ' + r.status);
    }

    function _apiDebugInfo() {
        return {
            hasMusicKitGlobal: typeof MusicKit !== 'undefined',
            hasInstance: !!music,
            hasApi: !!(music && music.api),
            hasDevToken: !!devToken,
            hasUserToken: !!userToken,
            localStorageKeys: (function() {
                try {
                    var keys = [];
                    for (var i = 0; i < localStorage.length; i++)
                        keys.push(localStorage.key(i));
                    return keys;
                } catch(e) { return []; }
            })()
        };
    }
"""


def save_debug_screenshot(driver: webdriver.Chrome, name: str) -> None:
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


def dismiss_cookie_consent(driver: webdriver.Chrome) -> None:
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


def create_driver() -> webdriver.Chrome:
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

                // 攔截 MusicKit.configure 以擷取 developer token。
                // TuneMyMusic 的 React 元件在選擇 Apple Music 時呼叫
                // MusicKit.configure({developerToken: ...})，
                // 此攔截器將 token 保存至 localStorage 供後續 API 呼叫使用。
                (function() {
                    var _origDefProp = Object.defineProperty;
                    // MusicKit 可能尚未載入，用 defineProperty 攔截其設定
                    var _hooked = false;
                    function hookConfigure(MK) {
                        if (_hooked || !MK || !MK.configure) return;
                        _hooked = true;
                        var orig = MK.configure.bind(MK);
                        MK.configure = function(config) {
                            if (config && config.developerToken) {
                                try {
                                    localStorage.setItem(
                                        '__tmm_apple_dev_token',
                                        config.developerToken
                                    );
                                } catch(e) {}
                            }
                            return orig(config);
                        };
                    }
                    // 若 MusicKit 已存在，直接 hook
                    if (typeof MusicKit !== 'undefined') {
                        hookConfigure(MusicKit);
                    }
                    // 監聽 MusicKit 被設定到 window 上的時機
                    try {
                        var _mkVal = window.MusicKit;
                        _origDefProp(window, 'MusicKit', {
                            configurable: true,
                            get: function() { return _mkVal; },
                            set: function(v) {
                                _mkVal = v;
                                if (v && v.configure) hookConfigure(v);
                            }
                        });
                    } catch(e) {}
                })();
            """
        },
    )
    return driver


def wait_and_click(
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


def wait_for_element(
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
