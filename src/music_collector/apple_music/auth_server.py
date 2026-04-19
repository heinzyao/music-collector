"""Apple Music MusicKit 授權模組。

macOS 主路線（run_osascript_auth）：
    以真實 Chrome 開啟 music.apple.com，透過 AppleScript 注入 JS 直接呼叫
    MusicKit.authorize()，在 Apple 自己的 domain 完成授權，繞過 origin 限制
    與 bot 偵測。使用獨立的 data/auth_profile 避免 Selenium profile 污染。

備援路線（run_auth_server，非 macOS 時）：
    啟動 localhost:8765 HTTP 伺服器提供授權頁面。
    注意：Apple Music 的 developerToken 有 origin 限制，此路線在 music.apple.com
    以外的 domain 呼叫 authorize() 可能失敗。

用法：
    python -m music_collector.apple_music.auth_server
    (或透過 ./recover-apple-music-sync.sh)
"""

import json
import re
import subprocess
import sys
import threading
import time
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import httpx

TOKEN_FILE = Path("data/apple_music_tokens.json")
AUTH_PORT = 8765
MUSICKIT_JS_URL = "https://js-cdn.music.apple.com/musickit/v3/musickit.js"
_JWT_RE = re.compile(r"eyJ[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}")

# 獨立 Chrome profile（與舊 Selenium browser_profile 隔離）
_AUTH_PROFILE = Path("data/auth_profile")

_APPLESCRIPT_TMPL = """\
tell application "Google Chrome"
    set _result to ""
    repeat with w in windows
        repeat with t in tabs of w
            if URL of t contains "music.apple.com" then
                set _result to execute t javascript {js_json}
                exit repeat
            end if
        end repeat
        if _result is not "" then exit repeat
    end repeat
    return _result
end tell
"""

_TRIGGER_JS = """(function(){
  try {
    var mk = MusicKit.getInstance();
    if (!mk) return "no_instance";
    if (mk.isAuthorized && mk.musicUserToken) return "already_authorized";
    mk.authorize()
      .then(function(t){ window.__mc_token = t; })
      .catch(function(e){ window.__mc_error = String(e); });
    return "triggered";
  } catch(e) { return "error:" + String(e); }
})()"""

_EXTRACT_JS = """(function(){
  try {
    var mk = MusicKit.getInstance();
    var ut = (mk && mk.musicUserToken) ? mk.musicUserToken : window.__mc_token;
    var dt = mk ? mk.developerToken : null;
    if (ut) return JSON.stringify({devToken:dt, userToken:ut,
                                   isAuthorized:!!(mk&&mk.isAuthorized)});
    return JSON.stringify({error: window.__mc_error || "no_token",
                           isAuthorized: !!(mk&&mk.isAuthorized)});
  } catch(e) { return JSON.stringify({error: String(e)}); }
})()"""


def _run_applescript(js: str, timeout: int = 20) -> str:
    script = _APPLESCRIPT_TMPL.format(js_json=json.dumps(js))
    r = subprocess.run(
        ["osascript", "-e", script],
        capture_output=True, text=True, timeout=timeout,
    )
    return r.stdout.strip()


def _save_token(data: dict) -> None:
    data["extracted_at"] = datetime.now(timezone.utc).isoformat()
    TOKEN_FILE.parent.mkdir(parents=True, exist_ok=True)
    TOKEN_FILE.write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
    )


# ── 主路線：osascript + 真實 Chrome ──


def run_osascript_auth() -> tuple[str, str] | tuple[None, None]:
    """macOS 專用：以真實 Chrome 開啟 music.apple.com，透過 AppleScript 觸發
    MusicKit.authorize()，在 Apple 自己的 domain 完成授權。
    """
    _AUTH_PROFILE.mkdir(parents=True, exist_ok=True)

    print("[1/4] 開啟 Apple Music（真實 Chrome，獨立 profile）...")
    subprocess.run(
        [
            "open", "-na", "Google Chrome", "--args",
            f"--user-data-dir={_AUTH_PROFILE.resolve()}",
            "--profile-directory=Default",
            "--no-first-run",
            "--no-default-browser-check",
            "--disable-default-apps",
            "--new-window",
            "https://music.apple.com/",
        ],
        check=False,
    )

    print("[2/4] 等待 MusicKit 初始化（20 秒）...")
    time.sleep(20)

    # 觸發 MusicKit.authorize()，最多重試 6 次等待初始化
    trigger_result = ""
    for attempt in range(6):
        try:
            trigger_result = _run_applescript(_TRIGGER_JS)
        except Exception as e:
            trigger_result = f"osascript_error:{e}"

        # 列出 Chrome 目前所有分頁 URL（除錯用）
        if not trigger_result or trigger_result == "no_instance":
            try:
                tab_list = subprocess.run(
                    ["osascript", "-e",
                     'tell application "Google Chrome"\n'
                     '  set u to {}\n'
                     '  repeat with w in windows\n'
                     '    repeat with t in tabs of w\n'
                     '      set end of u to URL of t\n'
                     '    end repeat\n'
                     '  end repeat\n'
                     '  return u as string\n'
                     'end tell'],
                    capture_output=True, text=True, timeout=10,
                ).stdout.strip()
                print(f"  Chrome 分頁：{tab_list[:120] or '(無視窗)' }")
            except Exception:
                pass

        if trigger_result and trigger_result not in ("", "no_instance"):
            break
        print(f"  MusicKit 尚未就緒（{attempt + 1}/6），再等 8 秒...")
        time.sleep(8)

    print(f"[3/4] authorize() 觸發結果：{trigger_result}")

    if not trigger_result or "error" in trigger_result or trigger_result == "no_instance":
        print("[ERROR] MusicKit 未初始化或觸發失敗。")
        print("        請確認 Chrome 已完整載入 music.apple.com 後重試。")
        return None, None

    if trigger_result != "already_authorized":
        print()
        print("=" * 60)
        print("Apple ID 登入視窗已在 Chrome 中開啟。")
        print("請完成登入：Email → 密碼 → 雙重認證碼")
        print("看到頭像後再等 3 秒，然後按 Enter。")
        print("=" * 60)
        input()

    # 提取 token，最多重試 5 次
    for attempt in range(5):
        if attempt > 0:
            time.sleep(3)
        try:
            raw = _run_applescript(_EXTRACT_JS)
            data = json.loads(raw)
        except Exception as e:
            print(f"  Attempt {attempt + 1}/5 解析失敗：{e}")
            continue

        if data.get("userToken"):
            _save_token(data)
            print(f"\n[4/4] Token 已儲存至 {TOKEN_FILE}")
            return data.get("devToken"), data["userToken"]

        print(
            f"  Attempt {attempt + 1}/5："
            f"{data.get('error', 'no token yet')}"
            f" (isAuthorized={data.get('isAuthorized')})"
        )

    print("[WARN] 無法取得 token，請確認已完成 Apple ID 登入。")
    return None, None


# ── 備援路線：localhost HTTP 伺服器 ──


def fetch_developer_token() -> str | None:
    """從 music.apple.com Vite JS bundle 提取 developerToken（JWT）。"""
    ua = (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    )
    headers = {"User-Agent": ua, "Accept-Language": "en-US,en;q=0.9"}
    try:
        resp = httpx.get(
            "https://music.apple.com/",
            headers=headers, timeout=20, follow_redirects=True,
        )
        m = re.search(_JWT_RE.pattern, resp.text)
        if m:
            return m.group(0)
        bundle_paths = re.findall(r'src="(/assets/index[^"]*\.js[^"]*)"', resp.text)
        if not bundle_paths:
            bundle_paths = re.findall(r'src="(/assets/[^"]*\.js[^"]*)"', resp.text)
        for path in bundle_paths[:3]:
            try:
                js = httpx.get(
                    f"https://music.apple.com{path}", headers=headers, timeout=30
                )
                m = re.search(_JWT_RE.pattern, js.text)
                if m:
                    return m.group(0)
            except Exception:
                continue
    except Exception as e:
        print(f"[WARN] 取得 Developer Token 失敗：{e}")
    return None


_AUTH_PAGE = """\
<!DOCTYPE html>
<html lang="zh-Hant">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Apple Music 授權 — Music Collector</title>
<style>
body{{font-family:-apple-system,BlinkMacSystemFont,sans-serif;display:flex;
  flex-direction:column;align-items:center;justify-content:center;
  min-height:100vh;margin:0;background:#f5f5f7;color:#1d1d1f;}}
.card{{background:#fff;border-radius:20px;padding:40px 48px;max-width:420px;
  width:90%;box-shadow:0 4px 24px rgba(0,0,0,.08);text-align:center;}}
h1{{font-size:22px;font-weight:700;margin:0 0 8px;}}
p{{color:#555;font-size:15px;line-height:1.6;margin:0 0 28px;}}
button{{padding:14px 32px;font-size:17px;font-weight:600;background:#fa2d55;
  color:#fff;border:none;border-radius:12px;cursor:pointer;transition:opacity .15s;}}
button:hover{{opacity:.88;}} button:disabled{{background:#ccc;cursor:default;}}
#status{{margin-top:20px;font-size:14px;color:#444;min-height:20px;}}
.ok{{color:#1e8a1e;font-weight:600;}} .err{{color:#c0392b;}}
</style>
</head>
<body>
<div class="card">
  <h1>Music Collector</h1>
  <p>點擊下方按鈕，在彈出的 Apple 登入視窗中完成驗證：<br>
     Apple ID &rarr; 密碼 &rarr; 雙重認證碼</p>
  <button id="btn" onclick="doAuth()">授權 Apple Music</button>
  <div id="status">正在載入 MusicKit…</div>
</div>
<script src="{musickit_js}"></script>
<script>
var _devToken = "{dev_token}";
document.addEventListener("musickitloaded", function() {{
  try {{
    MusicKit.configure({{developerToken:_devToken,
      app:{{name:"MusicCollector",build:"1.0"}}}});
    document.getElementById("status").textContent = "MusicKit 就緒，請點擊授權按鈕。";
  }} catch(e) {{
    document.getElementById("status").className = "err";
    document.getElementById("status").textContent =
      "MusicKit 設定失敗：" + (e&&(e.message||JSON.stringify(e))||String(e));
  }}
}});
async function doAuth() {{
  var btn=document.getElementById("btn"), st=document.getElementById("status");
  btn.disabled=true; st.className=""; st.textContent="正在開啟 Apple ID 登入視窗…";
  try {{
    var mk=MusicKit.getInstance();
    var userToken=await mk.authorize();
    st.textContent="授權成功，正在儲存…";
    var r=await fetch("/token",{{method:"POST",
      headers:{{"Content-Type":"application/json"}},
      body:JSON.stringify({{devToken:mk.developerToken,
        userToken:userToken,isAuthorized:mk.isAuthorized}})}});
    if(r.ok){{ st.className="ok"; st.textContent="✓ 完成！Token 已儲存，可關閉此視窗。"; }}
    else {{ st.className="err"; st.textContent="伺服器錯誤，請重試。"; btn.disabled=false; }}
  }} catch(e) {{
    st.className="err";
    st.textContent="授權失敗：" +
      (e&&(e.message||e.errorCode||JSON.stringify(e))||String(e));
    btn.disabled=false;
  }}
}}
</script>
</body>
</html>
"""


def run_auth_server(port: int = AUTH_PORT) -> tuple[str, str] | tuple[None, None]:
    """備援：localhost HTTP 授權伺服器。"""
    print("\n正在從 Apple Music 取得 Developer Token...")
    dev_token = fetch_developer_token()
    if not dev_token:
        print("[ERROR] 無法取得 Developer Token。")
        return None, None
    print(f"Developer Token 取得成功（長度 {len(dev_token)}）")

    result: dict = {}
    shutdown_event = threading.Event()
    html = _AUTH_PAGE.format(musickit_js=MUSICKIT_JS_URL, dev_token=dev_token)

    class _Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt, *args):
            pass

        def do_GET(self):
            body = html.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_POST(self):
            if self.path != "/token":
                self.send_response(404)
                self.end_headers()
                return
            length = int(self.headers.get("Content-Length", 0))
            try:
                result.update(json.loads(self.rfile.read(length)))
            except Exception:
                pass
            self.send_response(200)
            self.end_headers()
            shutdown_event.set()

    httpd = HTTPServer(("127.0.0.1", port), _Handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    url = f"http://localhost:{port}/"
    print(f"授權頁面：{url}")
    if sys.platform == "darwin":
        subprocess.run(["open", url], check=False)
    else:
        subprocess.run(["xdg-open", url], check=False)
    print("\n請在瀏覽器中點擊「授權 Apple Music」按鈕（最多等待 5 分鐘）。\n")
    shutdown_event.wait(timeout=300)
    httpd.shutdown()

    if result.get("userToken"):
        _save_token(result)
        print(f"Token 已儲存至 {TOKEN_FILE}")
        return result["devToken"], result["userToken"]
    print("[WARN] 授權逾時或未完成。")
    return None, None


# ── 入口：macOS 用 osascript，其他平台用 localhost server ──

if __name__ == "__main__":
    if sys.platform == "darwin":
        dev, user = run_osascript_auth()
    else:
        dev, user = run_auth_server()
    sys.exit(0 if (dev and user) else 1)
