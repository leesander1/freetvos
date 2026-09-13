"""The first-run wizard.

Four steps and a way out of each. Nothing here is compulsory: somebody who
wants to skip straight to watching can, and the tile brings it back.

The keyboard is the page's own, not the system's. Plasma ships one, the
compositor reports it as available and active, and it never draws itself; a
television whose wifi password cannot be typed is not set up at all.
"""
import html
import json

import tvui

WELCOME_BODY = """
<h1>Welcome</h1>
<p class="step">Two things and you are watching.</p>
<div class="rows" id="rows">
  <div class="row act sel"><div class="k">Set up the television</div></div>
  <div class="row act"><div class="k">Skip for now</div></div>
</div>
<p class="note">Joining a network, then choosing the apps you use. Both can be
changed later, and this can be run again from Setup on the home screen.</p>
<style>.note{font-size:22px;color:var(--dim);max-width:880px;line-height:1.5;
             margin-top:30px}</style>
<script>
__NAV__
const cells = [...document.querySelectorAll('.row')];
tvnav(cells, i => { location.href = i === 0 ? '/network' : '/skip'; }, null);
</script>
"""

NETWORK_BODY = """
<h1>Network</h1>
<p class="step" id="step">__STEP__</p>
<div class="rows" id="rows"></div>
<div class="msg" id="msg"></div>
<p class="hint">Enter chooses. Back goes to the previous step.</p>
<script>
__NAV__
__KB__
let ITEMS = __ITEMS__;
const rows = document.getElementById('rows');
const msg = document.getElementById('msg');
let busy = false;

function draw() {
  rows.innerHTML = '';
  ITEMS.forEach(it => {
    const el = document.createElement('div');
    el.className = it.kind === 'action' ? 'row act' : 'row';
    if (it.kind === 'action') {
      el.innerHTML = '<div class="k"></div>';
      el.querySelector('.k').textContent = it.label;
    } else {
      el.innerHTML = '<div class="k"></div><div class="v"></div>';
      el.querySelector('.k').textContent = it.label;
      el.querySelector('.v').textContent = it.note || '';
    }
    rows.appendChild(el);
  });
  tvnav([...rows.children], choose, () => { location.href = '/'; });
}

function join(ssid, password) {
  busy = true;
  msg.className = 'msg';
  msg.textContent = 'Joining ' + ssid + '\\u2026';
  fetch('/join', { method: 'POST',
                   body: JSON.stringify({ ssid: ssid, password: password }) })
    .then(r => r.json())
    .then(r => {
      busy = false;
      if (r.ok) { location.href = '/apps'; return; }
      msg.className = 'msg bad';
      msg.textContent = r.error || 'Could not join.';
    });
}

function choose(i) {
  if (busy) return;
  const it = ITEMS[i];
  if (it.kind === 'action') { location.href = it.go; return; }
  if (!it.secured) { join(it.label, ''); return; }
  tvkeyboard({
    label: it.label + ' password',
    mask: true,
    onDone: v => { if (v) join(it.label, v); else draw(); },
    onCancel: draw,
  });
}

function rescan() {
  msg.className = 'msg';
  msg.textContent = 'Looking\\u2026';
  fetch('/scan', { method: 'POST', body: '{}' })
    .then(r => r.json())
    .then(r => { ITEMS = r.items; msg.textContent = ''; draw(); });
}

draw();
</script>
"""

APPS_BODY = """
<h1>Apps</h1>
<p class="step">Pick the ones you use. Enter adds and removes.</p>
<div class="grid" id="grid"></div>
<div class="msg" id="msg"></div>
<p class="hint">Netflix, Prime Video, Disney+, Hulu, Apple TV+,
Paramount+, Peacock, ESPN+, YouTube, YouTube TV, Plex and Jellyfin are already
here. Back goes to the previous step.</p>
<script>
__NAV__
const ITEMS = __ITEMS__;
const grid = document.getElementById('grid');
const msg = document.getElementById('msg');
let busy = false;

function initial(name) {
  const m = name.match(/[A-Za-z0-9]/);
  return (m ? m[0] : '?').toUpperCase();
}

function build(it) {
  const tile = document.createElement('div');
  tile.className = 'tile';
  if (it.action) {
    tile.className = 'card action';
    tile.textContent = it.label;
    return { tile: tile, flag: null };
  }
  const icon = document.createElement('img');
  icon.alt = '';
  icon.src = '/icon/freetvos-' + it.id + '.svg';
  let tried = false;
  icon.addEventListener('error', () => {
    if (!tried) { tried = true; icon.src = '/icon/freetvos-' + it.id + '.png'; return; }
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
  sub.textContent = it.group;
  const flag = document.createElement('div');
  flag.className = 'flag';
  tile.append(icon, label, sub, flag);
  return { tile: tile, flag: flag };
}

const tiles = ITEMS.map(it => {
  const made = build(it);
  grid.appendChild(made.tile);
  return made;
});

function paint() {
  tiles.forEach((t, i) => {
    if (t.flag) t.flag.textContent = ITEMS[i].on ? '\\u2713 Added' : '';
  });
}

function choose(i) {
  const it = ITEMS[i];
  if (it.action) { location.href = it.go; return; }
  if (busy) return;
  busy = true;
  const adding = !it.on;
  msg.className = 'msg';
  msg.textContent = (adding ? 'Adding ' : 'Removing ') + it.name + '\\u2026';
  fetch('/app', { method: 'POST',
                  body: JSON.stringify({ id: it.id, on: adding }) })
    .then(r => r.json())
    .then(r => {
      busy = false;
      if (r.error) { msg.className = 'msg bad'; msg.textContent = r.error; return; }
      it.on = adding;
      msg.textContent = it.name + (adding ? ' added' : ' removed');
      paint();
    });
}

paint();
tvnav([...grid.children], choose, () => { location.href = '/network'; }, 1);
</script>
"""

DONE_BODY = """
<h1>All set</h1>
<p class="step" id="step">__STEP__</p>
<div class="rows">
  <div class="row act sel"><div class="k">Start watching</div></div>
</div>
<p class="note">Two more things worth knowing. <b>Library</b> signs into Plex or
Jellyfin and plays anything on a USB drive. <b>Inputs</b> shows a console or a
set-top box plugged into a USB capture device.</p>
<style>.note{font-size:22px;color:var(--dim);max-width:900px;line-height:1.6;
             margin-top:30px}.note b{color:var(--text)}</style>
<script>
__NAV__
tvnav([...document.querySelectorAll('.row')],
      () => { fetch('/finish', { method: 'POST', body: '{}' }); }, null);
</script>
"""


def run(setup) -> int:
    app = tvui.App("Setup")
    state = {"skipped": False}

    def network_items():
        items = []
        if setup.wired_connected():
            items.append({"kind": "action", "label": "Connected by cable",
                          "go": "/apps"})
        for network in setup.networks():
            note = "Joined" if network["in_use"] else (
                f"{network['signal']}%"
                + ("" if network["secured"] else "  open"))
            items.append({"kind": "network", "label": network["ssid"],
                          "note": note, "secured": network["secured"]})
        if not setup.wifi_device() and not setup.wired_connected():
            items.append({"kind": "action",
                          "label": "No network adapter found", "go": "/apps"})
        items.append({"kind": "action", "label": "Skip the network for now",
                      "go": "/apps"})
        return items

    def welcome(_query):
        return WELCOME_BODY.replace("__NAV__", tvui.NAV_JS)

    def network(_query):
        items = network_items()
        if setup.online():
            step = "Already online. Choose another network, or carry on."
        elif setup.wifi_device():
            step = "Choose a network."
        else:
            step = "Nothing to join here."
        return (NETWORK_BODY
                .replace("__NAV__", tvui.NAV_JS)
                .replace("__KB__", tvui.KEYBOARD_JS)
                .replace("__STEP__", html.escape(step))
                .replace("__ITEMS__", json.dumps(items)))

    def apps(_query):
        service = setup.services()
        have = service.installed()
        items = [{"id": entry["id"], "name": entry["name"],
                  "group": entry["group"], "on": entry["id"] in have}
                 for entry in service.catalog()]
        # First, not last. Twenty tiles between here and the end of the step
        # is a long way to travel to say you are finished, and the highlight
        # starts on the first app so the page still opens on something to pick.
        items.insert(0, {"action": True, "label": "Done with apps",
                         "go": "/done"})
        return (APPS_BODY
                .replace("__NAV__", tvui.NAV_JS)
                .replace("__ITEMS__", json.dumps(items)))

    def finished(_query):
        where = setup.current_network()
        if setup.wired_connected():
            step = "Connected by cable."
        elif where:
            step = f"Joined {where}."
        elif setup.online():
            step = "Online."
        else:
            step = "No network yet. Setup on the home screen will try again."
        return DONE_BODY.replace("__NAV__", tvui.NAV_JS).replace(
            "__STEP__", html.escape(step))

    def skip(_query):
        state["skipped"] = True
        setup.mark_done()
        return ('<h1>Skipped</h1><p class="step">Setup is on the home screen '
                'whenever you want it.</p><script>setTimeout(() => '
                'fetch("/finish", {method:"POST",body:"{}"}), 1500);</script>')

    def do_join(payload):
        ssid = (payload.get("ssid") or "").strip()
        if not ssid:
            return {"error": "No network chosen."}
        joined, reason = setup.connect(ssid, payload.get("password") or "")
        return {"ok": True} if joined else {"error": reason}

    def do_scan(_payload):
        return {"items": network_items()}

    def do_app(payload):
        service = setup.services()
        entry = next((c for c in service.catalog()
                      if c["id"] == payload.get("id")), None)
        if entry is None:
            return {"error": "That app is no longer in the catalogue."}
        if payload.get("on"):
            service.add(entry["id"], entry["name"], entry["url"],
                        entry.get("drm", "no"), entry["category"])
        else:
            service.remove(entry["id"])
        return {"ok": True}

    def do_finish(_payload):
        setup.mark_done()
        return {"ok": True}

    app.get("/", welcome)
    app.get("/network", network)
    app.get("/apps", apps)
    app.get("/done", finished)
    app.get("/skip", skip)
    app.post("/join", do_join)
    app.post("/scan", do_scan)
    app.post("/app", do_app)
    app.post("/finish", do_finish, finish=True)
    app.run()

    # Written whichever way the wizard ended, including the viewer walking away
    # from it. A wizard that comes back every boot until it is completed is a
    # wizard nobody can get past.
    setup.mark_done()
    return 0
