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
import urllib.parse
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

 /* Posters, for things that have artwork rather than an icon. */
 .tile.poster{width:212px}
 .tile.poster img{width:188px;height:282px;border-radius:10px;
                  object-fit:cover;margin-bottom:12px}
 .tile.poster .ph{width:188px;height:282px;border-radius:10px;
                  margin-bottom:12px}
 /* How far through something is, drawn along the bottom of its poster. */
 .bar{height:6px;background:#2A3242;border-radius:3px;margin-top:10px}
 .bar i{display:block;height:6px;background:var(--accent);border-radius:3px}
 .section{font-size:26px;margin:34px 0 14px;color:var(--dim)}
 .section:first-of-type{margin-top:0}

 /* Score cards: two teams, a score each, and what is happening. */
 .card{width:400px;background:var(--surface);border-radius:18px;padding:20px 22px;
       border:4px solid transparent;transition:border-color 90ms}
 .card.sel{border-color:var(--accent);box-shadow:0 0 26px rgba(61,220,151,.4)}
 .card .top{display:flex;align-items:center;gap:10px;font-size:17px;
            color:var(--dim);margin-bottom:14px}
 .card .top .star{color:var(--accent)}
 .card .team{display:flex;align-items:center;gap:12px;padding:7px 0}
 .card .team img{width:42px;height:42px;object-fit:contain}
 .card .team .rk{font-size:16px;color:var(--dim);min-width:26px}
 .card .team .ab{font-size:25px;flex:1}
 .card .team .rec{font-size:16px;color:var(--dim)}
 .card .team .sc{font-size:30px;font-weight:600;min-width:60px;text-align:right}
 .card .team.lost .ab,.card .team.lost .sc{color:var(--dim)}
 .card .foot{margin-top:14px;font-size:19px;color:var(--dim)}
 .card.live .foot{color:var(--accent)}
 .card .sit{font-size:17px;color:var(--dim);margin-top:6px}
 .card.action{display:flex;align-items:center;justify-content:center;
              min-height:186px;font-size:24px}

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


# Arrow-key movement over whatever is on screen, worked out from where things
# actually are rather than from a column count. A page with two grids of
# different tile sizes has no single column count, and guessing one sends the
# focus sideways off the end of a row into nothing.
NAV_JS = """
function tvnav(cells, onChoose, onBack, start) {
  // A starting position, so a page that rebuilds itself on a timer can put the
  // highlight back where the viewer left it rather than at the top.
  let index = Math.min(Math.max(start || 0, 0), cells.length - 1);
  function centre(el) {
    const r = el.getBoundingClientRect();
    return { x: r.left + r.width / 2, y: r.top + r.height / 2 };
  }
  function move(dx, dy) {
    const from = centre(cells[index]);
    let best = -1, bestScore = Infinity;
    cells.forEach((el, i) => {
      if (i === index) return;
      const to = centre(el);
      const ax = (to.x - from.x) * dx, ay = (to.y - from.y) * dy;
      // Must be in the direction asked for, and mostly in that direction.
      const along = ax + ay;
      if (along <= 1) return;
      const across = Math.abs(dx ? to.y - from.y : to.x - from.x);
      const score = along + across * 3;
      if (score < bestScore) { bestScore = score; best = i; }
    });
    if (best >= 0) { index = best; render(); }
  }
  function render() {
    cells.forEach((el, i) => el.classList.toggle('sel', i === index));
    cells[index].scrollIntoView({ block: 'nearest', inline: 'nearest' });
  }
  const handler = e => {
    if (e.key === 'ArrowRight') move(1, 0);
    else if (e.key === 'ArrowLeft') move(-1, 0);
    else if (e.key === 'ArrowDown') move(0, 1);
    else if (e.key === 'ArrowUp') move(0, -1);
    else if (e.key === 'Enter') onChoose(index);
    else if (e.key === 'Backspace' && onBack) onBack();
    else return;
    e.preventDefault();
  };
  // Only one keymap at a time. A page that rebuilds itself would otherwise
  // stack a listener per rebuild, and every arrow press would then be handled
  // several times over, by handlers pointing at elements no longer on screen.
  if (window.__tvnavHandler) removeEventListener('keydown', window.__tvnavHandler);
  window.__tvnavHandler = handler;
  addEventListener('keydown', handler);
  render();
  return {
    current: () => index,
    to: n => { index = Math.min(Math.max(n, 0), cells.length - 1); render(); },
  };
}
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
        """handler(query) -> html body, where query is a dict of parameters"""
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
                query = dict(urllib.parse.parse_qsl(
                    urlparse(self.path).query, keep_blank_values=True))
                try:
                    body = handler(query)
                except Exception as exc:                      # noqa: BLE001
                    # A blank browser window is the least useful thing a
                    # television can show, and there is no console here to find
                    # out what went wrong from.
                    body = ('<h1>Something went wrong</h1><p class="step">'
                            + str(exc)[:300] + "</p>")
                self._send(200, page(app.title, body).encode())

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
