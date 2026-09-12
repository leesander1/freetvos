"""The on-screen pages for your own media.

One page shape for everything. A USB drive, a Plex library and a Jellyfin
library are different underneath and identical to look at: a grid of things,
some of which you open and some of which you play. The place being looked at is
carried in the address as an opaque location, so the page never needs to know
which kind it is.
"""
import json
import os
import urllib.parse

import tvui

HOME_BODY = """
<h1>Library</h1>
<p class="step" id="step">__STEP__</p>
__SECTIONS__
<div class="msg" id="msg"></div>
<p class="hint">Arrow keys to move, Enter to choose, Back to leave.</p>
<script>
__NAV__
const ENTRIES = __ENTRIES__;
const cells = [...document.querySelectorAll('.tile')];
const msg = document.getElementById('msg');

function choose(i) {
  const it = ENTRIES[i];
  if (it.go) { location.href = it.go; return; }
  msg.className = 'msg';
  msg.textContent = 'Playing ' + it.title + '\\u2026';
  fetch('/play', { method: 'POST', body: JSON.stringify({ ref: it.ref }) })
    .then(r => r.json())
    .then(r => {
      if (r.error) { msg.className = 'msg bad'; msg.textContent = r.error; }
    });
}
if (cells.length) tvnav(cells, choose, null);
</script>
"""

LIST_BODY = """
<h1>__TITLE__</h1>
<p class="step">__STEP__</p>
<div class="grid" id="grid"></div>
<p class="empty" id="empty" hidden>Nothing here.</p>
<div class="msg" id="msg"></div>
<p class="hint">Enter opens or plays. Backspace goes back.</p>
<style>.empty{font-size:24px;color:var(--dim)}</style>
<script>
__NAV__
const ENTRIES = __ENTRIES__;
const UP = __UP__;
const grid = document.getElementById('grid');
const msg = document.getElementById('msg');

ENTRIES.forEach(it => {
  const tile = document.createElement('div');
  tile.className = 'tile' + (it.thumb ? ' poster' : '');
  if (it.thumb) {
    const img = document.createElement('img');
    img.src = it.thumb; img.alt = '';
    img.addEventListener('error', () => {
      const ph = document.createElement('span');
      ph.className = 'ph';
      ph.textContent = (it.title.match(/[A-Za-z0-9]/) || ['?'])[0].toUpperCase();
      img.replaceWith(ph);
    });
    tile.appendChild(img);
  } else {
    const ph = document.createElement('span');
    ph.className = 'ph';
    ph.textContent = it.kind === 'folder' ? '\\u2026'
      : (it.title.match(/[A-Za-z0-9]/) || ['?'])[0].toUpperCase();
    tile.appendChild(ph);
  }
  const label = document.createElement('div');
  label.className = 'lbl';
  label.textContent = it.title;
  tile.appendChild(label);
  if (it.sub) {
    const sub = document.createElement('div');
    sub.className = 'sub'; sub.textContent = it.sub;
    tile.appendChild(sub);
  }
  if (it.progress) {
    const bar = document.createElement('div');
    bar.className = 'bar';
    const fill = document.createElement('i');
    fill.style.width = Math.round(it.progress * 100) + '%';
    bar.appendChild(fill);
    tile.appendChild(bar);
  }
  grid.appendChild(tile);
});
document.getElementById('empty').hidden = ENTRIES.length > 0;

const cells = [...grid.children];
function choose(i) {
  const it = ENTRIES[i];
  if (it.go) { location.href = it.go; return; }
  msg.className = 'msg';
  msg.textContent = 'Playing ' + it.title + '\\u2026';
  fetch('/play', { method: 'POST', body: JSON.stringify({ ref: it.ref }) })
    .then(r => r.json())
    .then(r => {
      if (r.error) { msg.className = 'msg bad'; msg.textContent = r.error; }
    });
}
function back() { location.href = UP; }
if (cells.length) tvnav(cells, choose, back);
else addEventListener('keydown', e => {
  if (e.key === 'Backspace') { back(); e.preventDefault(); }
});
</script>
"""

CODE_BODY = """
<h1>__TITLE__</h1>
<p class="step">__STEP__</p>
<div class="code" id="code">__CODE__</div>
<p class="where">__WHERE__</p>
<div class="msg" id="msg">Waiting&hellip;</div>
<p class="hint">Backspace goes back.</p>
<style>
 .code{font-size:104px;letter-spacing:14px;font-weight:600;
       color:var(--accent);margin:30px 0 20px}
 .where{font-size:26px;color:var(--text);max-width:900px;line-height:1.5}
</style>
<script>
const msg = document.getElementById('msg');
let stop = false;
function poll() {
  if (stop) return;
  fetch('/link-check', { method: 'POST', body: '{}' })
    .then(r => r.json())
    .then(r => {
      if (r.done) {
        stop = true;
        msg.textContent = r.message || 'Signed in';
        setTimeout(() => { location.href = '/'; }, 1400);
      } else if (r.error) {
        stop = true; msg.className = 'msg bad'; msg.textContent = r.error;
      } else {
        setTimeout(poll, 2000);
      }
    })
    .catch(() => setTimeout(poll, 3000));
}
setTimeout(poll, 2000);
addEventListener('keydown', e => {
  if (e.key === 'Backspace') { stop = true; location.href = '/'; }
});
</script>
"""

ADDRESS_BODY = """
<h1>Sign in to Jellyfin</h1>
<p class="step">Where is the server?</p>
<div class="rows" id="rows">
  <div class="row sel" id="r0">
    <div class="k">Address</div>
    <input id="addr" type="text" placeholder="jellyfin.local:8096" autocomplete="off">
  </div>
  <div class="row act" id="r1"><div class="k">Connect</div></div>
</div>
<div class="msg" id="msg"></div>
<p class="hint">Up and down to move. Backspace goes back.</p>
<script>
let index = 0;
const rows = [document.getElementById('r0'), document.getElementById('r1')];
const addr = document.getElementById('addr');
const msg = document.getElementById('msg');
function render() {
  rows.forEach((el, i) => el.classList.toggle('sel', i === index));
  if (index === 0) addr.focus(); else addr.blur();
}
function submit() {
  if (!addr.value.trim()) {
    msg.className = 'msg bad';
    msg.textContent = 'An address is needed.';
    return;
  }
  msg.className = 'msg';
  msg.textContent = 'Looking for the server\\u2026';
  fetch('/jellyfin-start', {
    method: 'POST', body: JSON.stringify({ address: addr.value.trim() })
  }).then(r => r.json()).then(r => {
    if (r.error) { msg.className = 'msg bad'; msg.textContent = r.error; return; }
    location.href = '/link-jellyfin';
  });
}
addEventListener('keydown', e => {
  if (e.key === 'ArrowDown') index = Math.min(1, index + 1);
  else if (e.key === 'ArrowUp') index = Math.max(0, index - 1);
  else if (e.key === 'Enter') {
    if (index === 1) submit(); else index = 1;
    e.preventDefault(); render(); return;
  } else if (e.key === 'Backspace' && index !== 0) { location.href = '/'; }
  else return;
  e.preventDefault();
  render();
});
render();
</script>
"""


def _loc(value: str, up: str = "") -> str:
    """A link to somewhere, carrying where it was reached from.

    The parent travels in the address rather than being worked out on arrival.
    Two different places can hold the same folder, and a Plex episode list has
    no way at all to name the show it belongs to from its own identifier.
    """
    address = "/at?loc=" + urllib.parse.quote(value, safe="")
    if up:
        address += "&up=" + urllib.parse.quote(up, safe="")
    return address


def _seconds(value: int) -> str:
    if not value:
        return ""
    hours, rest = divmod(int(value), 3600)
    minutes = rest // 60
    return f"{hours}h {minutes:02d}m" if hours else f"{minutes} min"


def run(media) -> int:
    """media is the freetvos-media module, which owns every side effect."""
    app = tvui.App("Library")
    pending: dict = {}
    result: dict = {}

    # -- reading -----------------------------------------------------------

    def entries_at(loc: str) -> tuple:
        """(title, entries) for anywhere in the library."""
        if loc.startswith("usb:") or loc.startswith("folder:"):
            path = loc.split(":", 1)[1]
            out = []
            for item in media.list_folder(path):
                out.append({
                    "title": item["title"],
                    "kind": item["kind"],
                    "go": None if item["playable"]
                    else _loc(f"folder:{item['path']}", loc),
                    "ref": json.dumps({"source": "local", "path": item["path"],
                                       "title": item["title"]}),
                })
            name = path.rstrip("/").split("/")[-1] or "Files"
            return name.replace("_", " "), out

        if loc == "plex":
            base, token = media.plex_connect()
            if not base:
                return "Plex", []
            out = [{"title": lib["title"], "kind": "folder",
                    "go": _loc(f"plex-section:{lib['key']}", loc), "ref": ""}
                   for lib in media.plex.libraries(base, token,
                                                   media.client_id())]
            return "Plex", out

        if loc.startswith("plex-section:") or loc.startswith("plex-item:"):
            base, token = media.plex_connect()
            key = loc.split(":", 1)[1]
            if loc.startswith("plex-section:"):
                items = media.plex.library_items(base, token,
                                                 media.client_id(), key)
            else:
                items = media.plex.children(base, token, media.client_id(), key)
            return "Plex", [_plex_entry(media, base, token, i, loc)
                            for i in items]

        if loc == "jellyfin":
            account = media.jellyfin_account()
            out = [{"title": view["title"], "kind": "folder",
                    "go": _loc(f"jellyfin-item:{view['id']}", loc), "ref": ""}
                   for view in media.jellyfin.views(
                       account["base"], media.client_id(), account["token"],
                       account["user"])]
            return account.get("name", "Jellyfin"), out

        if loc.startswith("jellyfin-item:"):
            account = media.jellyfin_account()
            items = media.jellyfin.items(
                account["base"], media.client_id(), account["token"],
                account["user"], loc.split(":", 1)[1])
            return account.get("name", "Jellyfin"), \
                [_jellyfin_entry(media, account, i, loc) for i in items]

        return "Library", []

    def _plex_entry(media_mod, base, token, item, here):
        thumb = media_mod.plex.image_url(base, token, item["thumb"])
        progress = (item["offset"] / item["duration"]
                    if item["duration"] and item["offset"] else 0)
        return {
            "title": item["title"],
            "kind": item["kind"],
            "thumb": thumb,
            "sub": str(item["year"] or ""),
            "progress": progress,
            "go": None if item["playable"]
            else _loc(f"plex-item:{item['id']}", here),
            "ref": json.dumps({"source": "plex", "part": item["part"],
                               "title": item["title"],
                               "offset": item["offset"]}),
        }

    def _jellyfin_entry(media_mod, account, item, here):
        thumb = media_mod.jellyfin.image_url(account["base"], item["thumb"])
        progress = (item["offset"] / item["duration"]
                    if item["duration"] and item["offset"] else 0)
        return {
            "title": item["title"],
            "kind": item["kind"],
            "thumb": thumb,
            "sub": str(item["year"] or ""),
            "progress": progress,
            "go": None if item["playable"]
            else _loc(f"jellyfin-item:{item['id']}", here),
            "ref": json.dumps({"source": "jellyfin", "id": item["id"],
                               "title": item["title"],
                               "offset": item["offset"]}),
        }

    # -- pages -------------------------------------------------------------

    def home():
        entries = []
        sections = []

        resume = media.resume_everywhere()
        if resume:
            tiles = []
            for item in resume:
                thumb = ""
                if item["source"] == "plex":
                    base, token = media.plex_base()
                    thumb = media.plex.image_url(base, token,
                                                 item.get("thumb", ""))
                elif item["source"] == "jellyfin":
                    account = media.jellyfin_account()
                    thumb = media.jellyfin.image_url(account["base"],
                                                     item.get("thumb", ""))
                progress = (item["offset"] / item["duration"]
                            if item.get("duration") else 0)
                ref = {"source": item["source"], "title": item["title"],
                       "offset": item.get("offset", 0)}
                if item["source"] == "plex":
                    ref["part"] = item.get("part", "")
                elif item["source"] == "jellyfin":
                    ref["id"] = item["id"]
                else:
                    ref["path"] = item["path"]
                entries.append({"title": item["title"], "go": None,
                                "ref": json.dumps(ref)})
                tiles.append(_tile_html(item["title"], thumb,
                                        _seconds(item.get("offset", 0)),
                                        progress))
            sections.append('<div class="section">Continue watching</div>'
                            '<div class="grid">' + "".join(tiles) + "</div>")

        tiles = []
        for source in media.sources():
            loc = source["id"] if source["kind"] in ("plex", "jellyfin") \
                else f"{source['kind']}:{source['path']}"
            entries.append({"title": source["name"], "go": _loc(loc),
                            "ref": ""})
            tiles.append(_tile_html(source["name"], "", _source_note(source), 0))

        if not media.plex_account().get("token"):
            entries.append({"title": "Sign in to Plex", "go": "/link-plex",
                            "ref": ""})
            tiles.append(_tile_html("Plex", "", "Sign in", 0))
        if not media.jellyfin_account().get("token"):
            entries.append({"title": "Sign in to Jellyfin",
                            "go": "/jellyfin-address", "ref": ""})
            tiles.append(_tile_html("Jellyfin", "", "Sign in", 0))

        sections.append('<div class="section">Where to look</div>'
                        '<div class="grid">' + "".join(tiles) + "</div>")

        step = ("Nothing is connected yet."
                if not media.sources()
                else "Pick up where you left off, or look somewhere")
        return (HOME_BODY
                .replace("__NAV__", tvui.NAV_JS)
                .replace("__STEP__", step)
                .replace("__SECTIONS__", "".join(sections))
                .replace("__ENTRIES__", json.dumps(entries)))

    def _source_note(source):
        return {"usb": "USB drive", "folder": "Folder",
                "plex": "Server", "jellyfin": "Server"}.get(source["kind"], "")

    def _tile_html(title, thumb, sub, progress):
        import html as _html
        classes = "tile poster" if thumb else "tile"
        initial = next((c for c in title.upper() if c.isalnum()), "?")
        picture = (f'<img src="{_html.escape(thumb, quote=True)}" alt="">'
                   if thumb else f'<span class="ph">{initial}</span>')
        bar = (f'<div class="bar"><i style="width:{round(progress * 100)}%">'
               "</i></div>") if progress else ""
        return (f'<div class="{classes}">{picture}'
                f'<div class="lbl">{_html.escape(title)}</div>'
                f'<div class="sub">{_html.escape(sub)}</div>{bar}</div>')

    def listing(query):
        loc = query.get("loc", "")
        up = query.get("up", "")
        up = _loc(up) if up else "/"
        try:
            title, entries = entries_at(loc)
        except Exception as exc:                              # noqa: BLE001
            title, entries = "Library", []
            print(f"listing {loc}: {exc}")
        return (LIST_BODY
                .replace("__NAV__", tvui.NAV_JS)
                .replace("__TITLE__", title)
                .replace("__STEP__",
                         f"{len(entries)} item{'' if len(entries) == 1 else 's'}"
                         if entries else "Nothing here")
                .replace("__UP__", json.dumps(up))
                .replace("__ENTRIES__", json.dumps(entries)))

    def link_plex():
        identity = media.client_id()
        pin = media.plex.request_pin(identity)
        pending.clear()
        pending.update({"kind": "plex", "id": pin["id"]})
        return (CODE_BODY
                .replace("__TITLE__", "Sign in to Plex")
                .replace("__STEP__", "On your phone or computer")
                .replace("__CODE__", pin["code"])
                .replace("__WHERE__", "Go to plex.tv/link and enter this code. "
                                      "Your password is typed there, never here."))

    def link_jellyfin():
        account = pending.get("jellyfin") or {}
        if not account.get("code"):
            return ADDRESS_BODY
        return (CODE_BODY
                .replace("__TITLE__", "Sign in to Jellyfin")
                .replace("__STEP__", f"On another device signed into "
                                     f"{account.get('name', 'Jellyfin')}")
                .replace("__CODE__", account["code"])
                .replace("__WHERE__", "Open Jellyfin, go to your account's "
                                      "Quick Connect page and approve this "
                                      "code."))

    # -- actions -----------------------------------------------------------

    def do_play(payload):
        try:
            ref = json.loads(payload.get("ref") or "{}")
        except ValueError:
            return {"error": "Could not work out what to play."}
        if not ref:
            return {"error": "Nothing to play."}
        argv = media.play_target(ref)
        result.update({"argv": argv})
        return {"ok": True}

    def do_link_check(_payload):
        if pending.get("kind") == "plex":
            token = media.plex.poll_pin(media.client_id(), pending["id"])
            if not token:
                return {"waiting": True}
            media._write("plex", {"token": token})
            base, _ = media.plex_connect(refresh=True)
            if not base:
                return {"error": "Signed in, but no server answered."}
            name = (media.plex_account().get("server") or {}).get("name", "Plex")
            return {"done": True, "message": f"Signed in to {name}"}

        account = pending.get("jellyfin") or {}
        if account.get("secret"):
            if not media.jellyfin.quick_connect_check(
                    account["base"], media.client_id(), account["secret"]):
                return {"waiting": True}
            session = media.jellyfin.quick_connect_finish(
                account["base"], media.client_id(), account["secret"])
            media._write("jellyfin", {"base": account["base"],
                                      "name": account.get("name", "Jellyfin"),
                                      "token": session["token"],
                                      "user": session["user"]})
            return {"done": True,
                    "message": f"Signed in as {session['name']}"}
        return {"waiting": True}

    def do_jellyfin_start(payload):
        base = media.jellyfin.normalise_address(payload.get("address", ""))
        if not base:
            return {"error": "An address is needed."}
        info = media.jellyfin.identify(base, media.client_id())
        start = media.jellyfin.quick_connect_start(base, media.client_id())
        pending.clear()
        pending["jellyfin"] = {"base": base, "name": info["name"],
                               "code": start["code"], "secret": start["secret"]}
        return {"ok": True}

    app.get("/", lambda _q: home())
    app.get("/at", listing)
    app.get("/link-plex", lambda _q: link_plex())
    app.get("/jellyfin-address", lambda _q: ADDRESS_BODY)
    app.get("/link-jellyfin", lambda _q: link_jellyfin())
    app.post("/play", do_play, finish=True)
    app.post("/link-check", do_link_check)
    app.post("/jellyfin-start", do_jellyfin_start)

    app.run()
    if result.get("argv"):
        os.execv(result["argv"][0], result["argv"])
    return 0
