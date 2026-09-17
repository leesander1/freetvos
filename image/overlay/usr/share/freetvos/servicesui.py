"""The on-screen page for adding and removing services.

A catalogue you walk with the arrow keys, because typing a web address with a
d-pad is miserable and most people want one of the same twenty services. The
address field is there for everything else, and Plasma's on-screen keyboard
serves it, so it needs no keyboard plugged into the television.
"""
import json

import tvui

CATALOGUE_BODY = """
<h1>Apps</h1>
<p class="step" id="step">Enter adds an app. Enter again on an added one removes it.</p>
<div class="grid" id="grid"></div>
<div class="msg" id="msg"></div>
<p class="hint">Arrow keys to move, Enter to choose, Back to leave.</p>
<script>
const ITEMS = __ITEMS__;
let index = 0;
let busy = false;
const grid = document.getElementById('grid');
const msg = document.getElementById('msg');
const tiles = ITEMS.map(it => {
  const t = build(it);
  grid.appendChild(t.tile);
  return t;
});

function initial(name) {
  const m = name.match(/[A-Za-z0-9]/);
  return (m ? m[0] : '?').toUpperCase();
}

// Built as nodes rather than as markup, so the icon is requested once. An
// innerHTML rebuilt on every keypress re-fetches every image, which on a
// catalogue this size is visible as a flicker all the way down the page.
function build(it) {
  const tile = document.createElement('div');
  tile.className = 'tile';

  const icon = document.createElement('img');
  icon.alt = '';
  icon.src = it.custom ? '/icon/freetvos-add.svg'
                       : '/icon/freetvos-' + it.id + '.svg';
  let triedPng = false;
  icon.addEventListener('error', () => {
    // An app that has not been added yet has no icon: its own is only fetched
    // from the service when someone asks for it. A letter is a better answer
    // than an empty square.
    if (!triedPng && !it.custom) {
      triedPng = true;
      icon.src = '/icon/freetvos-' + it.id + '.png';
      return;
    }
    const ph = document.createElement('span');
    ph.className = 'ph';
    ph.textContent = initial(it.name);
    icon.replaceWith(ph);
  });

  const label = document.createElement('div');
  label.className = 'lbl';
  label.textContent = it.name;

  const sub = document.createElement('div');
  sub.className = 'sub';
  sub.textContent = it.custom ? 'Anything with a web address' : it.group;

  const flag = document.createElement('div');
  flag.className = 'flag';

  tile.append(icon, label, sub, flag);
  return { tile: tile, flag: flag };
}

function render() {
  tiles.forEach((t, i) => {
    t.tile.classList.toggle('sel', i === index);
    t.flag.textContent = ITEMS[i].installed ? '\u2713 Added' : '';
  });
  tiles[index].tile.scrollIntoView({ block: 'center' });
}

function choose() {
  const it = ITEMS[index];
  if (it.custom) { location.href = '/custom'; return; }
  if (busy) return;
  busy = true;
  const adding = !it.installed;
  msg.className = 'msg';
  msg.textContent = (adding ? 'Adding ' : 'Removing ') + it.name + '\u2026';
  fetch(adding ? '/add' : '/remove',
        { method: 'POST', body: JSON.stringify({ id: it.id }) })
    .then(r => r.json())
    .then(r => {
      busy = false;
      if (r.error) {
        msg.className = 'msg bad';
        msg.textContent = r.error;
        return;
      }
      it.installed = adding;
      msg.textContent = it.name + (adding ? ' is on the home screen'
                                          : ' was removed');
      if (adding) {
        // The icon exists now; ask for it again rather than making someone
        // reopen the page to see it.
        const fresh = build(it);
        grid.replaceChild(fresh.tile, tiles[index].tile);
        tiles[index] = fresh;
      }
      render();
    });
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

CUSTOM_BODY = """
<h1>Add an app</h1>
<p class="step">Any site that plays in a browser can be a tile.</p>
<div class="rows" id="rows">
  <div class="row" id="r0">
    <div class="k">Name</div>
    <input id="name" type="text" placeholder="Jellyfin" autocomplete="off">
  </div>
  <div class="row" id="r1">
    <div class="k">Web address</div>
    <input id="url" type="url" placeholder="jellyfin.local:8096" autocomplete="off">
  </div>
  <div class="row" id="r2">
    <div class="k">Needs Widevine for protected video</div>
    <div class="v" id="drmv">No</div>
    <div class="arrows">&lsaquo; &rsaquo;</div>
  </div>
  <div class="row act" id="r3"><div class="k">Add it</div></div>
</div>
<div class="msg" id="msg"></div>
<p class="hint">Enter on a field to type in it. Up and down to move. Back
returns to the list.</p>
<script>
__KB__
let index = 0;
let drm = false;
const rows = [0, 1, 2, 3].map(i => document.getElementById('r' + i));
const name = document.getElementById('name');
const url = document.getElementById('url');
const msg = document.getElementById('msg');
// Read-only to the browser. Focusing a field was meant to raise the system's
// keyboard, which never draws on this shell, so the fields could not be filled
// from a remote at all. Typing goes through the page's own keyboard instead.
name.readOnly = true;
url.readOnly = true;

function render() {
  rows.forEach((el, i) => el.classList.toggle('sel', i === index));
  document.getElementById('drmv').textContent = drm ? 'Yes' : 'No';
}

function type(field, label) {
  tvkeyboard({
    label: label,
    value: field.value,
    onDone: v => { field.value = v.trim(); index = Math.min(3, index + 1); render(); },
    onCancel: () => render(),
  });
}

function submit() {
  if (!name.value.trim() || !url.value.trim()) {
    msg.className = 'msg bad';
    msg.textContent = 'A name and a web address are both needed.';
    return;
  }
  msg.className = 'msg';
  msg.textContent = 'Adding \\u2026';
  fetch('/custom-add', {
    method: 'POST',
    body: JSON.stringify({ name: name.value.trim(), url: url.value.trim(),
                           drm: drm })
  }).then(r => r.json()).then(r => {
    if (r.error) {
      msg.className = 'msg bad';
      msg.textContent = r.error;
      return;
    }
    msg.textContent = r.name + ' is on the home screen';
    setTimeout(() => { location.href = '/'; }, 1200);
  });
}

const pageKeys = e => {
  if (e.key === 'ArrowDown') index = Math.min(3, index + 1);
  else if (e.key === 'ArrowUp') index = Math.max(0, index - 1);
  else if (e.key === 'ArrowLeft' && index === 2) drm = !drm;
  else if (e.key === 'ArrowRight' && index === 2) drm = !drm;
  else if (e.key === 'Enter') {
    e.preventDefault();
    if (index === 3) { submit(); return; }
    if (index === 2) { drm = !drm; render(); return; }
    if (index === 0) { type(name, 'Name'); return; }
    type(url, 'Web address');
    return;
  } else if (e.key === 'Backspace') { location.href = '/'; }
  else return;
  e.preventDefault();
  render();
};
// Registered under the name the keyboard looks for, so it is set aside while
// the keyboard is open and handed back when it closes.
window.__tvnavHandler = pageKeys;
addEventListener('keydown', pageKeys);
render();
</script>
"""
CUSTOM_BODY = CUSTOM_BODY.replace("__KB__", tvui.KEYBOARD_JS)


def run(svc) -> int:
    """svc is the freetvos-service module, which owns every side effect."""
    app = tvui.App("Apps")

    def items():
        have = svc.installed()
        out = [{"id": entry["id"], "name": entry["name"],
                "group": entry["group"], "installed": entry["id"] in have}
               for entry in svc.catalog()]
        out.append({"id": "_custom", "name": "Add by web address",
                    "group": "", "installed": False, "custom": True})
        return out

    app.get("/", lambda _q: CATALOGUE_BODY.replace("__ITEMS__",
                                                   json.dumps(items())))
    app.get("/custom", lambda _q: CUSTOM_BODY)

    def do_add(payload):
        entry = next((c for c in svc.catalog()
                      if c["id"] == payload.get("id")), None)
        if entry is None:
            return {"error": "That app is no longer in the catalogue."}
        svc.add(entry["id"], entry["name"], entry["url"],
                entry.get("drm", "no"), entry["category"],
                agent=entry.get("agent", ""))
        return {"ok": True}

    def do_remove(payload):
        if not svc.remove(payload.get("id", "")):
            return {"error": "That app came with the system and cannot be "
                             "removed here."}
        return {"ok": True}

    def do_custom(payload):
        name = (payload.get("name") or "").strip()
        address = (payload.get("url") or "").strip()
        if not name or not address:
            return {"error": "A name and a web address are both needed."}
        if "://" not in address:
            address = "https://" + address
        result = svc.add(svc.slug(name), name, address,
                         "yes" if payload.get("drm") else "no",
                         "AudioVideo;Video;Player;")
        return {"ok": True, "name": result["name"]}

    app.post("/add", do_add)
    app.post("/remove", do_remove)
    app.post("/custom-add", do_custom)
    app.run()
    return 0
