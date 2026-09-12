"""The two on-screen pages for external inputs: the source list and its settings.

Served over localhost and opened fullscreen in Chromium, the same way the split
view picker works. A page rather than a native dialog because the rest of this
television is already pages: it inherits the same d-pad handling, the same type
sizes and the same palette for free, and nothing here needs a toolkit.

Both pages live in one server so moving between them is a navigation rather than
a second browser launch, which on modest hardware is the difference between
instant and a two second pause.
"""
import http.server
import json
import os
import socket
import subprocess
import threading
from pathlib import Path
from urllib.parse import urlparse

ICONS = Path("/usr/share/icons/hicolor/scalable/apps")

NAME_PRESETS = [
    ("", "Automatic"),
    ("HDMI 1", "HDMI 1"), ("HDMI 2", "HDMI 2"),
    ("HDMI 3", "HDMI 3"), ("HDMI 4", "HDMI 4"),
    ("Game console", "Game console"), ("PlayStation", "PlayStation"),
    ("Xbox", "Xbox"), ("Nintendo", "Nintendo"),
    ("Blu-ray", "Blu-ray"), ("Cable box", "Cable box"),
    ("Computer", "Computer"), ("Camera", "Camera"),
]

ASPECTS = [("auto", "As the source sends it"), ("16:9", "16:9"),
           ("4:3", "4:3"), ("fill", "Fill the screen"), ("zoom", "Zoom")]

DEINTERLACE = [("auto", "Only when needed"), ("yes", "Always"), ("no", "Never")]

# No "tell me" option. Bigscreen's shell puts nothing on screen for a
# notification, so the setting would have been a promise this system cannot
# keep; see the note in freetvos-hdmi's say().
ON_CONNECT = [("switch", "Switch to it"), ("ignore", "Do nothing")]

LATENCIES = [("0", "None"), ("20", "20 ms"), ("40", "40 ms"),
             ("80", "80 ms"), ("120", "120 ms"), ("200", "200 ms")]

HEIGHTS = [("720", "Up to 720p"), ("1080", "Up to 1080p"),
           ("2160", "Up to 2160p")]

YESNO = [("no", "No"), ("yes", "Yes")]

GLOBAL_HEADER = """# How external inputs behave. Written by the settings page;
# safe to edit by hand.
"""

DEVICE_HEADER = """# Settings for one capture device, keyed by how the device
# identifies itself. Written by the settings page.
"""

STYLE = """
 :root{--bg:#0B0E14;--surface:#151A23;--accent:#3DDC97;--text:#E6EAF2;
       --dim:#8C97AB}
 *{box-sizing:border-box}
 [hidden]{display:none!important}
 body{margin:0;background:var(--bg);color:var(--text);
      font:16px system-ui,-apple-system,"Noto Sans",sans-serif;
      /* 5% inset keeps everything inside TV title-safe */
      padding:5vh 5vw}
 h1{font-size:44px;margin:0 0 6px}
 p.step{color:var(--dim);font-size:24px;margin:0 0 40px}
 .hint{margin-top:40px;color:var(--dim);font-size:20px}
"""


def _page(body: str) -> str:
    return ('<!doctype html><meta charset="utf-8"><title>Inputs</title>'
            '<style>' + STYLE + '</style>' + body)


# ---------------------------------------------------------------------------
# The source list.
# ---------------------------------------------------------------------------

SOURCES_BODY = """
<style>
 .grid{display:flex;flex-wrap:wrap;gap:28px}
 .tile{width:250px;background:var(--surface);border-radius:18px;padding:24px;
       text-align:center;border:4px solid transparent;transition:border-color 90ms}
 .tile.sel{border-color:var(--accent);box-shadow:0 0 26px rgba(61,220,151,.4)}
 .tile img{width:112px;height:112px;display:block;margin:0 auto 16px}
 .tile.away img{opacity:.35}
 .tile .lbl{font-size:22px}
 .tile .sub{font-size:17px;color:var(--dim);margin-top:8px}
 .empty{font-size:24px;color:var(--dim);max-width:820px;line-height:1.5}
 .msg{margin-top:32px;font-size:22px;color:var(--accent);min-height:28px}
</style>
<h1>Inputs</h1>
<p class="step" id="step">Choose what to watch</p>
<div class="grid" id="grid"></div>
<p class="empty" id="empty" hidden>
  Nothing is plugged in yet. Connect a USB HDMI capture device, then plug the
  console or set-top box into it. Most dongles need no drivers and appear here
  within a couple of seconds.
</p>
<div class="msg" id="msg"></div>
<p class="hint">Arrow keys to move, Enter to choose, Back to leave.</p>
<script>
const ITEMS = __ITEMS__;
let index = 0;
const grid = document.getElementById('grid');
const msg = document.getElementById('msg');

ITEMS.forEach(it => {
  const d = document.createElement('div');
  d.className = 'tile' + (it.present === false ? ' away' : '');
  d.innerHTML = '<img src="/icon/' + it.icon + '.svg" alt="">'
              + '<div class="lbl">' + it.label + '</div>'
              + '<div class="sub">' + it.sub + '</div>';
  grid.appendChild(d);
});
document.getElementById('empty').hidden = ITEMS.length > 1;

function render() {
  [...grid.children].forEach((el, i) => el.classList.toggle('sel', i === index));
}

function choose() {
  const it = ITEMS[index];
  if (it.action === 'settings') { location.href = '/settings'; return; }
  if (it.present === false) {
    msg.textContent = 'Nothing is connected to ' + it.label + '.';
    return;
  }
  msg.textContent = 'Opening ' + it.label + '\\u2026';
  fetch('/open', { method: 'POST', body: JSON.stringify({ key: it.key }) });
}

addEventListener('keydown', e => {
  const cols = Math.max(1, Math.floor(grid.clientWidth / 278));
  if (e.key === 'ArrowRight') index = Math.min(ITEMS.length - 1, index + 1);
  else if (e.key === 'ArrowLeft') index = Math.max(0, index - 1);
  else if (e.key === 'ArrowDown') index = Math.min(ITEMS.length - 1, index + cols);
  else if (e.key === 'ArrowUp') index = Math.max(0, index - cols);
  else if (e.key === 'Enter') { choose(); e.preventDefault(); return; }
  else return;
  e.preventDefault();
  render();
});
render();
</script>
"""


def sources_model(ctl) -> list:
    items = []
    for it in ctl.inputs():
        if it["role"] != "input":
            continue
        if it["present"]:
            mode = ctl.chosen_mode(it) if it["modes"] else None
            sub = ctl.mode_label(mode) if mode else "Ready"
            if it["card"] < 0:
                sub += " · no sound"
        else:
            sub = "Not connected"
        items.append({"key": it["key"], "label": it["label"], "sub": sub,
                      "present": it["present"], "icon": "freetvos-hdmi"})
    items.append({"key": "", "label": "Settings", "sub": "Inputs and sound",
                  "action": "settings", "present": True,
                  "icon": "freetvos-settings"})
    return items


# ---------------------------------------------------------------------------
# Settings.
# ---------------------------------------------------------------------------

SETTINGS_BODY = """
<style>
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
 .row.act .k{flex:0;font-size:24px}
 .msg{margin-top:26px;font-size:22px;color:var(--accent);min-height:28px}
</style>
<h1>Input settings</h1>
<p class="step">Up and down to move, left and right to change</p>
<div class="rows" id="rows"></div>
<div class="msg" id="msg"></div>
<p class="hint">Back returns to the input list. Changes are kept when you save.</p>
<script>
const ROWS = __ROWS__;
const rows = document.getElementById('rows');
const msg = document.getElementById('msg');
let index = ROWS.findIndex(r => r.kind !== 'header');

ROWS.forEach(r => {
  const el = document.createElement('div');
  if (r.kind === 'header') {
    el.className = 'hdr';
    el.innerHTML = r.text + (r.sub ? '<span class="sub">' + r.sub + '</span>' : '');
  } else if (r.kind === 'action') {
    el.className = 'row act';
    el.innerHTML = '<div class="k">' + r.label + '</div>';
  } else {
    el.className = 'row';
    el.innerHTML = '<div class="k">' + r.label + '</div>'
                 + '<div class="v"></div><div class="arrows"></div>';
  }
  rows.appendChild(el);
});

function optionIndex(r) {
  const i = r.options.findIndex(o => o[0] === r.value);
  return i < 0 ? 0 : i;
}

function render() {
  ROWS.forEach((r, i) => {
    const el = rows.children[i];
    el.classList.toggle('sel', i === index);
    if (r.kind !== 'field') return;
    const oi = optionIndex(r);
    el.querySelector('.v').textContent = r.options[oi][1];
    el.querySelector('.arrows').textContent =
      r.options.length > 1 ? '\\u2039 \\u203a' : '';
  });
  rows.children[index].scrollIntoView({ block: 'center' });
}

function step(delta) {
  let i = index;
  for (;;) {
    i += delta;
    if (i < 0 || i >= ROWS.length) return;
    if (ROWS[i].kind !== 'header') { index = i; return; }
  }
}

function cycle(delta) {
  const r = ROWS[index];
  if (r.kind !== 'field') return;
  const n = r.options.length;
  r.value = r.options[(optionIndex(r) + delta + n) % n][0];
}

function save() {
  const values = ROWS.filter(r => r.kind === 'field')
                     .map(r => ({ dev: r.dev || '', key: r.key, value: r.value }));
  msg.textContent = 'Saving\\u2026';
  fetch('/save', { method: 'POST', body: JSON.stringify({ values: values }) })
    .then(() => { location.href = '/'; });
}

addEventListener('keydown', e => {
  if (e.key === 'ArrowDown') step(1);
  else if (e.key === 'ArrowUp') step(-1);
  else if (e.key === 'ArrowRight') cycle(1);
  else if (e.key === 'ArrowLeft') cycle(-1);
  else if (e.key === 'Enter') {
    if (ROWS[index].kind === 'action') { save(); e.preventDefault(); return; }
  } else if (e.key === 'Backspace') { location.href = '/'; }
  else return;
  e.preventDefault();
  render();
});
render();
</script>
"""


def _mode_options(ctl, item) -> list:
    """The sizes and rates this device offers, best first and deduplicated.

    Capped, because a capture card can enumerate well over a hundred
    combinations and a list that long cannot be walked with a remote.
    """
    seen, uniq = set(), []
    for m in item["modes"]:
        sig = (m["w"], m["h"], m["fps"], m["fourcc"])
        if sig in seen:
            continue
        seen.add(sig)
        uniq.append(m)
    uniq.sort(key=lambda m: (m["w"] * m["h"], m["fps"]), reverse=True)
    # What "automatic" resolves to right now, cap and all, rather than the
    # best the hardware can name.
    capped = dict(item, cfg=dict(item["cfg"], MODE="auto"))
    auto = ctl.chosen_mode(capped) if item["modes"] else None
    label = f"Automatic ({ctl.mode_label(auto)})" if auto else "Automatic"
    return [("auto", label)] + [(ctl.mode_spec(m), ctl.mode_label(m))
                                for m in uniq[:12]]


def _audio_options(ctl, item) -> list:
    cards = ctl.alsa_cards()
    if item["card"] >= 0:
        names = dict(cards)
        auto = f"From this device ({names.get(item['card'], item['card'])})"
    else:
        auto = "From this device (none found)"
    return ([("auto", auto), ("none", "No sound")]
            + [(str(i), label) for i, label in cards])


def settings_model(ctl) -> list:
    rows = []
    for item in ctl.inputs():
        cfg = item["cfg"]
        if item["present"]:
            hardware = " ".join(x for x in (item["vendor"], item["product"])
                                if x) or item["name"]
            sub = f"{hardware} on {item['devnode']}"
        else:
            sub = "Remembered, but not plugged in"
        rows.append({"kind": "header", "text": item["label"], "sub": sub})
        rows.append({"kind": "field", "dev": item["key"], "key": "ROLE",
                     "label": "Use this device",
                     "options": [("input", "As an input"),
                                 ("ignore", "Ignore it")],
                     "value": item["role"]})
        rows.append({"kind": "field", "dev": item["key"], "key": "NAME",
                     "label": "Name", "options": NAME_PRESETS,
                     "value": cfg["NAME"]})
        if item["present"]:
            rows.append({"kind": "field", "dev": item["key"], "key": "MODE",
                         "label": "Picture", "options": _mode_options(ctl, item),
                         "value": cfg["MODE"]})
            rows.append({"kind": "field", "dev": item["key"], "key": "AUDIO",
                         "label": "Sound", "options": _audio_options(ctl, item),
                         "value": cfg["AUDIO"]})
        rows.append({"kind": "field", "dev": item["key"], "key": "ASPECT",
                     "label": "Shape", "options": ASPECTS,
                     "value": cfg["ASPECT"]})
        rows.append({"kind": "field", "dev": item["key"], "key": "DEINTERLACE",
                     "label": "Smooth interlaced video",
                     "options": DEINTERLACE, "value": cfg["DEINTERLACE"]})
        rows.append({"kind": "field", "dev": item["key"], "key": "ON_CONNECT",
                     "label": "When it is plugged in",
                     "options": [("inherit", "Same as all inputs")] + ON_CONNECT,
                     "value": cfg["ON_CONNECT"]})

    glob = ctl.config()
    rows.append({"kind": "header", "text": "All inputs",
                 "sub": "Applies to every capture device"})
    rows.append({"kind": "field", "dev": "", "key": "ON_CONNECT",
                 "label": "When a device is plugged in",
                 "options": ON_CONNECT, "value": glob["ON_CONNECT"]})
    rows.append({"kind": "field", "dev": "", "key": "AUDIO_LATENCY_MS",
                 "label": "Hold sound back to match the picture",
                 "options": LATENCIES, "value": glob["AUDIO_LATENCY_MS"]})
    rows.append({"kind": "field", "dev": "", "key": "MAX_HEIGHT",
                 "label": "Largest picture to ask for",
                 "options": HEIGHTS, "value": glob["MAX_HEIGHT"]})
    rows.append({"kind": "field", "dev": "", "key": "AUTO_OPEN_SINGLE",
                 "label": "Skip this list when only one input is connected",
                 "options": YESNO, "value": glob["AUTO_OPEN_SINGLE"]})
    rows.append({"kind": "action", "id": "save", "label": "Save and close"})

    # The page cycles through options by position, so they have to arrive as
    # pairs rather than as objects.
    #
    # A value that is not in its own option list is also repaired here. It
    # happens two ways: a name typed into the config file by hand, and a sound
    # card that was chosen once and has since been unplugged. Either way the
    # page would show the first option instead, and saving would quietly adopt
    # it, so the setting would be lost by looking at it.
    for r in rows:
        if r["kind"] != "field":
            continue
        r["options"] = [list(o) for o in r["options"]]
        if r["value"] not in [o[0] for o in r["options"]]:
            r["options"].insert(1, [r["value"], r["value"] or "Automatic"])
    return rows


def apply_values(ctl, values) -> None:
    per_device, globals_ = {}, {}
    for v in values:
        key, value = v.get("key"), v.get("value", "")
        if not key:
            continue
        if v.get("dev"):
            per_device.setdefault(v["dev"], {})[key] = value
        else:
            globals_[key] = value

    if globals_:
        current = ctl.read_conf(ctl.USER_CONF)
        current.update(globals_)
        ctl.write_conf(ctl.USER_CONF, current, GLOBAL_HEADER)
    for dev, vals in per_device.items():
        path = ctl.DEVICE_CONF / f"{dev}.conf"
        current = ctl.read_conf(path)
        current.update(vals)
        ctl.write_conf(path, current, DEVICE_HEADER)


# ---------------------------------------------------------------------------
# Serving.
# ---------------------------------------------------------------------------


def run(page: str, ctl) -> int:
    result: dict = {}
    done = threading.Event()

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
            if path == "/":
                body = SOURCES_BODY.replace(
                    "__ITEMS__", json.dumps(sources_model(ctl)))
                self._send(200, _page(body).encode())
                return
            if path == "/settings":
                body = SETTINGS_BODY.replace(
                    "__ROWS__", json.dumps(settings_model(ctl)))
                self._send(200, _page(body).encode())
                return
            if path.startswith("/icon/"):
                # Served from here rather than linked as file://, which a page
                # loaded over http is not allowed to reach.
                f = ICONS / Path(path).name
                if f.suffix == ".svg" and f.exists():
                    self._send(200, f.read_bytes(), "image/svg+xml")
                    return
            self._send(404)

        def do_POST(self):
            path = urlparse(self.path).path
            n = int(self.headers.get("Content-Length") or 0)
            try:
                payload = json.loads(self.rfile.read(n) or b"{}")
            except ValueError:
                payload = {}
            if path == "/save":
                apply_values(ctl, payload.get("values") or [])
                self._send(200, b"ok")
                return
            if path == "/open":
                result.update(payload)
                self._send(200, b"ok")
                done.set()
                return
            self._send(404)

    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()

    server = http.server.ThreadingHTTPServer(("127.0.0.1", port), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()

    profile = Path(os.environ.get("XDG_DATA_HOME",
                                  Path.home() / ".local/share")) \
        / "freetvos/webapps/_inputs"
    start = "/settings" if page == "settings" else "/"
    browser = subprocess.Popen([
        "/usr/bin/chromium-browser",
        f"--app=http://localhost:{port}{start}",
        f"--user-data-dir={profile}",
        # Not freetvos-<service>: split view treats those as panes, and a
        # settings page tiled alongside a film is not what anyone asked for.
        "--class=freetvos-hdmi-ui",
        "--ozone-platform=wayland",
        "--force-device-scale-factor=1",
        "--start-fullscreen",
        "--hide-scrollbars",
        "--password-store=basic",
        "--no-first-run",
    ])

    # Give up rather than hang forever if the window is closed or never appears.
    done.wait(timeout=900)
    server.shutdown()
    browser.terminate()
    try:
        browser.wait(timeout=5)
    except subprocess.TimeoutExpired:
        browser.kill()

    key = result.get("key")
    if not key:
        return 0

    item = next((i for i in ctl.inputs() if i["key"] == key), None)
    if item is None or not item["present"]:
        return 1
    argv = ctl.viewer_argv(item)
    os.execv(argv[0], argv)
    return 0
