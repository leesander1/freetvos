"""Shared machinery for the television's own on-screen pages.

Every settings surface here is a page served over localhost and opened
fullscreen in Chromium, rather than a native dialog. The services are web apps
already, so a page inherits the same d-pad handling and the same palette for
free, it can show the services' own icons without a toolkit, and one stylesheet
keeps every surface looking like the same product.

A page registers handlers and runs:

    app = tvui.App("Inputs")
    app.get("/", render)
    app.post("/save", save)
    app.post("/open", open_it, finish=True)
    result = app.run()

`finish` marks the handler that ends the session: its payload is what run()
returns, and the browser is closed behind it.
"""
import http.server
import json
import os
import socket
import subprocess
import threading
from pathlib import Path
from urllib.parse import urlparse

# Both trees, user first, so a service added on the device can carry its own
# icon without writing to the read-only image.
ICON_DIRS = [
    Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local/share"))
    / "icons/hicolor",
    Path("/usr/share/icons/hicolor"),
]
ICON_SIZES = ["scalable", "512x512", "256x256", "128x128", "64x64"]

# One stylesheet for every surface. The 5% inset is television title-safe: the
# outer edge of a panel is not reliably visible, and overscan on older sets eats
# more than that.
STYLE = """
 :root{--bg:#0B0E14;--surface:#151A23;--accent:#3DDC97;--alt:#4EA8FF;
       --text:#E6EAF2;--dim:#8C97AB}
 *{box-sizing:border-box}
 [hidden]{display:none!important}
 body{margin:0;background:var(--bg);color:var(--text);
      font:16px system-ui,-apple-system,"Noto Sans",sans-serif;
      padding:5vh 5vw}
 h1{font-size:44px;margin:0 0 6px}
 p.step{color:var(--dim);font-size:24px;margin:0 0 40px}
 .hint{margin-top:40px;color:var(--dim);font-size:20px}
 .msg{margin-top:26px;font-size:22px;color:var(--accent);min-height:28px}
 .msg.bad{color:#FF6B6B}

 /* Tiles: a grid of things to choose between. */
 .grid{display:flex;flex-wrap:wrap;gap:28px}
 .tile{width:250px;background:var(--surface);border-radius:18px;padding:24px;
       text-align:center;border:4px solid transparent;
       transition:border-color 90ms}
 .tile.sel{border-color:var(--accent);box-shadow:0 0 26px rgba(61,220,151,.4)}
 .tile img{width:112px;height:112px;display:block;margin:0 auto 16px;
           object-fit:contain}
 .tile.away img{opacity:.35}
 .tile .lbl{font-size:22px}
 .tile .sub{font-size:17px;color:var(--dim);margin-top:8px}
 .tile .flag{font-size:16px;color:var(--accent);margin-top:8px}
 /* Stands in for an icon that is not there yet, or never arrives. */
 .tile .ph{width:112px;height:112px;margin:0 auto 16px;border-radius:24px;
           background:#2A3242;color:var(--accent);font-size:58px;
           font-weight:600;display:flex;align-items:center;
           justify-content:center}

 /* Rows: a list of settings, one value each. */
 .rows{max-width:1100px}
 .hdr{font-size:28px;margin:38px 0 4px;color:var(--text)}
 .hdr:first-child{margin-top:0}
 .hdr .sub{display:block;font-size:18px;color:var(--dim);margin-top:4px}
 .row{display:flex;align-items:center;gap:24px;background:var(--surface);
      border-radius:14px;padding:18px 24px;margin-top:12px;
      border:4px solid transparent;transition:border-color 90ms}
 .row.sel{border-color:var(--accent)}
 .row .k{flex:1;font-size:22px}
 .row .v{font-size:22px;color:var(--accent)}
 .row .arrows{color:var(--dim);font-size:20px;width:44px;text-align:right}
 .row.act{justify-content:center}
 .row.act .k{flex:0 0 auto;font-size:24px;white-space:nowrap}
 .row input{flex:1;font-size:22px;background:#0B0E14;color:var(--text);
            border:2px solid #2A3242;border-radius:10px;padding:12px 16px}
"""


def page(title: str, body: str) -> str:
    return ('<!doctype html><meta charset="utf-8"><title>' + title
            + '</title><style>' + STYLE + '</style>' + body)


def find_icon(name: str):
    """An icon by theme name, from either tree, largest useful form first."""
    stem = Path(name).stem
    for root in ICON_DIRS:
        for size in ICON_SIZES:
            for ext, ctype in (("svg", "image/svg+xml"), ("png", "image/png")):
                f = root / size / "apps" / f"{stem}.{ext}"
                if f.exists():
                    return f, ctype
    return None, None


class App:
    """A set of routes, served to one fullscreen browser window."""

    def __init__(self, title: str):
        self.title = title
        self._get = {}
        self._post = {}
        self._finishers = set()
        self._result: dict = {}
        self._done = threading.Event()

    def get(self, path: str, handler) -> None:
        """handler() -> html body"""
        self._get[path] = handler

    def post(self, path: str, handler, finish: bool = False) -> None:
        """handler(payload) -> optional dict sent back as JSON"""
        self._post[path] = handler
        if finish:
            self._finishers.add(path)

    def _handler_class(self):
        app = self

        class Handler(http.server.BaseHTTPRequestHandler):
            def log_message(self, *_a):
                pass

            def _send(self, code, body=b"", ctype="text/html; charset=utf-8"):
                self.send_response(code)
                self.send_header("Content-Type", ctype)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                if body:
                    self.wfile.write(body)

            def do_GET(self):
                path = urlparse(self.path).path
                if path.startswith("/icon/"):
                    # Served from here rather than linked as file://, which a
                    # page loaded over http is not allowed to reach.
                    f, ctype = find_icon(Path(path).name)
                    if f:
                        self._send(200, f.read_bytes(), ctype)
                    else:
                        self._send(404)
                    return
                handler = app._get.get(path)
                if handler is None:
                    self._send(404)
                    return
                self._send(200, page(app.title, handler()).encode())

            def do_POST(self):
                path = urlparse(self.path).path
                handler = app._post.get(path)
                if handler is None:
                    self._send(404)
                    return
                n = int(self.headers.get("Content-Length") or 0)
                try:
                    payload = json.loads(self.rfile.read(n) or b"{}")
                except ValueError:
                    payload = {}
                try:
                    reply = handler(payload) or {}
                except Exception as exc:                 # noqa: BLE001
                    # A page that gets no answer looks frozen, and there is no
                    # console on a television to find out why.
                    reply = {"error": str(exc)}
                self._send(200, json.dumps(reply).encode(),
                           "application/json")
                if path in app._finishers and not reply.get("error"):
                    app._result = dict(payload)
                    app._done.set()

        return Handler

    def run(self, start: str = "/", timeout: float = 900.0) -> dict:
        sock = socket.socket()
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
        sock.close()

        server = http.server.ThreadingHTTPServer(("127.0.0.1", port),
                                                 self._handler_class())
        threading.Thread(target=server.serve_forever, daemon=True).start()

        profile = Path(os.environ.get("XDG_DATA_HOME",
                                      Path.home() / ".local/share")) \
            / "freetvos/webapps/_ui"
        browser = subprocess.Popen([
            "/usr/bin/chromium-browser",
            f"--app=http://localhost:{port}{start}",
            f"--user-data-dir={profile}",
            # Not freetvos-<service>: the split view treats those as panes, and
            # a settings page tiled beside a film is not what anyone asked for.
            "--class=freetvos-ui",
            "--ozone-platform=wayland",
            "--force-device-scale-factor=1",
            "--start-fullscreen",
            "--hide-scrollbars",
            # Let the compositor offer its on-screen keyboard to a focused
            # text field. A television has no other keyboard, and signing into
            # a service needs one. Configured and not confirmed: the keyboard
            # process runs, but it was never seen to appear over a Chromium
            # field in the VM.
            "--enable-wayland-ime",
            "--password-store=basic",
            "--no-first-run",
        ])

        # Give up rather than hang forever if the window is closed by the
        # remote's Back key, or never appears at all.
        self._done.wait(timeout=timeout)
        server.shutdown()
        browser.terminate()
        try:
            browser.wait(timeout=5)
        except subprocess.TimeoutExpired:
            browser.kill()
        return self._result
