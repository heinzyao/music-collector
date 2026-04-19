"""本機 MusicKit 授權伺服器。

啟動本機 HTTP 伺服器，在真實 Chrome（非 Selenium）中執行 MusicKit.authorize()，
完全繞過 Apple 的 bot 偵測問題，一次性取得 musicUserToken 並存至 token 檔案。

流程：
    1. 從 music.apple.com JS bundle 提取 developerToken
    2. 啟動 localhost:8765 伺服器，提供授權頁面
    3. 用 `open` 開啟真實瀏覽器（非 Selenium）
    4. 使用者點擊「授權 Apple Music」→ MusicKit.authorize() → Apple ID 登入
    5. 授權完成後頁面 POST token 至本機伺服器
    6. 伺服器儲存 token 至 data/apple_music_tokens.json 並關閉

用法：
    python -m music_collector.apple_music.auth_server
    (或透過 ./recover-apple-music-sync.sh)
"""

import json
import re
import subprocess
import sys
import threading
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import httpx

TOKEN_FILE = Path("data/apple_music_tokens.json")
AUTH_PORT = 8765
MUSICKIT_JS_URL = "https://js-cdn.music.apple.com/musickit/v3/musickit.js"

# JWT pattern: three base64url segments separated by dots
_JWT_RE = re.compile(r"eyJ[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}")

_AUTH_PAGE = """\
<!DOCTYPE html>
<html lang="zh-Hant">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Apple Music 授權 — Music Collector</title>
<style>
body{{font-family:-apple-system,BlinkMacSystemFont,sans-serif;
  display:flex;flex-direction:column;align-items:center;
  justify-content:center;min-height:100vh;margin:0;
  background:#f5f5f7;color:#1d1d1f;}}
.card{{background:#fff;border-radius:20px;padding:40px 48px;
  max-width:420px;width:90%;box-shadow:0 4px 24px rgba(0,0,0,.08);
  text-align:center;}}
h1{{font-size:22px;font-weight:700;margin:0 0 8px;}}
p{{color:#555;font-size:15px;line-height:1.6;margin:0 0 28px;}}
button{{padding:14px 32px;font-size:17px;font-weight:600;
  background:#fa2d55;color:#fff;border:none;border-radius:12px;
  cursor:pointer;transition:opacity .15s;}}
button:hover{{opacity:.88;}}
button:disabled{{background:#ccc;cursor:default;}}
#status{{margin-top:20px;font-size:14px;color:#444;min-height:20px;}}
.ok{{color:#1e8a1e;font-weight:600;}}
.err{{color:#c0392b;}}
</style>
</head>
<body>
<div class="card">
  <h1>Music Collector</h1>
  <p>點擊下方按鈕，在彈出的 Apple 登入視窗中完成驗證：<br>
     輸入 Apple ID &rarr; 密碼 &rarr; 雙重認證碼<br>
     完成後程式將自動繼續。</p>
  <button id="btn" onclick="doAuth()">授權 Apple Music</button>
  <div id="status">正在載入 MusicKit…</div>
</div>
<script src="{musickit_js}"></script>
<script>
var _devToken = "{dev_token}";

document.addEventListener("musickitloaded", function() {{
  try {{
    MusicKit.configure({{
      developerToken: _devToken,
      app: {{name: "MusicCollector", build: "1.0"}}
    }});
    document.getElementById("status").textContent = "MusicKit 就緒，請點擊授權按鈕。";
  }} catch(e) {{
    document.getElementById("status").className = "err";
    document.getElementById("status").textContent = "MusicKit 設定失敗：" + e.message;
  }}
}});

async function doAuth() {{
  var btn = document.getElementById("btn");
  var st = document.getElementById("status");
  btn.disabled = true;
  st.className = "";
  st.textContent = "正在開啟 Apple ID 登入視窗…";
  try {{
    var mk = MusicKit.getInstance();
    var userToken = await mk.authorize();
    st.textContent = "授權成功，正在儲存…";
    var r = await fetch("/token", {{
      method: "POST",
      headers: {{"Content-Type": "application/json"}},
      body: JSON.stringify({{
        devToken: mk.developerToken,
        userToken: userToken,
        isAuthorized: mk.isAuthorized
      }})
    }});
    if (r.ok) {{
      st.className = "ok";
      st.textContent = "✓ 完成！Token 已儲存，可關閉此視窗。";
    }} else {{
      st.className = "err";
      st.textContent = "伺服器回應錯誤，請重試。";
      btn.disabled = false;
    }}
  }} catch(e) {{
    st.className = "err";
    st.textContent = "授權失敗：" + e.message;
    btn.disabled = false;
  }}
}}
</script>
</body>
</html>
"""


def fetch_developer_token() -> str | None:
    """從 music.apple.com 的 Vite JS bundle 提取 Apple Music Developer Token（JWT）。

    流程：
    1. 取得主頁面，找到 /assets/index~*.js bundle URL
    2. 下載該 bundle，以 JWT regex 提取 developerToken
    """
    ua = (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    )
    headers = {"User-Agent": ua, "Accept-Language": "en-US,en;q=0.9"}

    try:
        resp = httpx.get(
            "https://music.apple.com/",
            headers=headers,
            timeout=20,
            follow_redirects=True,
        )

        # 先嘗試直接從 HTML 找（若未來 Apple 改回內嵌）
        m = re.search(_JWT_RE.pattern, resp.text)
        if m:
            return m.group(0)

        # 從頁面找 Vite main bundle URL：/assets/index~*.js
        bundle_paths = re.findall(r'src="(/assets/index[^"]*\.js[^"]*)"', resp.text)
        if not bundle_paths:
            bundle_paths = re.findall(r'src="(/assets/[^"]*\.js[^"]*)"', resp.text)

        for path in bundle_paths[:3]:
            url = f"https://music.apple.com{path}"
            try:
                js = httpx.get(url, headers=headers, timeout=30)
                m = re.search(_JWT_RE.pattern, js.text)
                if m:
                    return m.group(0)
            except Exception:
                continue

    except Exception as e:
        print(f"[WARN] 取得 Developer Token 失敗：{e}")

    return None


def run_auth_server(port: int = AUTH_PORT) -> tuple[str, str] | tuple[None, None]:
    """啟動本機授權伺服器，等待使用者完成 MusicKit 授權。

    Returns:
        (dev_token, user_token) 成功時；(None, None) 失敗或逾時。
    """
    print("\n[1/3] 正在從 Apple Music 取得 Developer Token...")
    dev_token = fetch_developer_token()
    if not dev_token:
        print("[ERROR] 無法取得 Developer Token，請確認網路連線並重試。")
        return None, None
    print(f"      Developer Token 取得成功（長度 {len(dev_token)}）")

    result: dict = {}
    shutdown_event = threading.Event()
    html = _AUTH_PAGE.format(musickit_js=MUSICKIT_JS_URL, dev_token=dev_token)

    class _Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt, *args):  # suppress access log
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
            body = self.rfile.read(length)
            try:
                data = json.loads(body)
                result.update(data)
                result["extracted_at"] = datetime.now(timezone.utc).isoformat()
            except Exception:
                pass
            self.send_response(200)
            self.end_headers()
            shutdown_event.set()

    httpd = HTTPServer(("127.0.0.1", port), _Handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()

    url = f"http://localhost:{port}/"
    print(f"[2/3] 授權頁面已啟動：{url}")

    if sys.platform == "darwin":
        subprocess.run(["open", url], check=False)
    else:
        subprocess.run(["xdg-open", url], check=False)

    print()
    print("=" * 60)
    print("瀏覽器已開啟授權頁面。")
    print("請點擊「授權 Apple Music」按鈕，完成 Apple ID 登入：")
    print("  Email → 密碼 → 雙重認證碼")
    print("完成後程式將自動繼續（最多等待 5 分鐘）。")
    print("=" * 60)
    print()

    shutdown_event.wait(timeout=300)
    httpd.shutdown()

    if result.get("userToken"):
        TOKEN_FILE.parent.mkdir(parents=True, exist_ok=True)
        TOKEN_FILE.write_text(
            json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(f"[3/3] Token 已儲存至 {TOKEN_FILE}")
        return result["devToken"], result["userToken"]

    print("[WARN] 授權逾時或未完成，Token 未儲存。")
    return None, None


if __name__ == "__main__":
    dev, user = run_auth_server()
    sys.exit(0 if (dev and user) else 1)
