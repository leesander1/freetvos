"""The on-screen page for picture, sound and the things you pair.

Rows rather than tiles, because these are settings with values rather than
things to choose between. Picture and output changes are applied on Enter and
not while cycling: stepping through screen modes and applying each one in turn
would black the television out several times on the way past.
"""
import json

import tvui

BODY = """
<h1>Picture &amp; Sound</h1>
<p class="step">Up and down to move, left and right to change</p>
<div class="rows" id="rows"></div>
<div class="msg" id="msg"></div>
<p class="hint" id="hint">Back returns to the home screen.</p>
<script>
__NAV__
let ROWS = __ROWS__;
const rowsEl = document.getElementById('rows');
const msg = document.getElementById('msg');
let index = 0;
let busy = false;

function build() {
  rowsEl.innerHTML = '';
  ROWS.forEach(r => {
    const el = document.createElement('div');
    if (r.kind === 'header') {
      el.className = 'hdr';
      el.innerHTML = r.text + (r.sub ? '<span class="sub">' + r.sub + '</span>' : '');
    } else if (r.kind === 'action') {
      el.className = 'row act';
      el.innerHTML = '<div class="k"></div>';
      el.querySelector('.k').textContent = r.label;
    } else {
      el.className = 'row';
      el.innerHTML = '<div class="k"></div><div class="v"></div>'
                   + '<div class="arrows"></div>';
      el.querySelector('.k').textContent = r.label;
    }
    rowsEl.appendChild(el);
  });
  if (ROWS[index] && ROWS[index].kind === 'header') step(1);
  render();
}

function optionIndex(r) {
  const i = r.options.findIndex(o => o[0] === r.value);
  return i < 0 ? 0 : i;
}

function render() {
  ROWS.forEach((r, i) => {
    const el = rowsEl.children[i];
    el.classList.toggle('sel', i === index);
    if (r.kind !== 'field') return;
    const oi = optionIndex(r);
    el.querySelector('.v').textContent = r.options[oi][1];
    el.querySelector('.arrows').textContent =
      r.options.length > 1 ? '\\u2039 \\u203a' : '';
  });
  const row = ROWS[index];
  document.getElementById('hint').textContent =
    row && row.apply === 'enter' ? 'Enter applies the change. Back leaves.'
                                 : 'Back returns to the home screen.';
  if (rowsEl.children[index]) {
    rowsEl.children[index].scrollIntoView({ block: 'center' });
  }
}

function step(delta) {
  let i = index;
  for (;;) {
    i += delta;
    if (i < 0 || i >= ROWS.length) return;
    if (ROWS[i].kind !== 'header') { index = i; return; }
  }
}

function send(path, body, note) {
  if (busy) return;
  busy = true;
  if (note) { msg.className = 'msg'; msg.textContent = note; }
  fetch(path, { method: 'POST', body: JSON.stringify(body) })
    .then(r => r.json())
    .then(r => {
      busy = false;
      if (r.error) { msg.className = 'msg bad'; msg.textContent = r.error; }
      else if (r.message) { msg.className = 'msg'; msg.textContent = r.message; }
      if (r.rows) { ROWS = r.rows; build(); }
    })
    .catch(() => { busy = false; });
}

function cycle(delta) {
  const r = ROWS[index];
  if (r.kind !== 'field') return;
  const n = r.options.length;
  r.value = r.options[(optionIndex(r) + delta + n) % n][0];
  render();
  if (r.apply === 'now') send('/set', { key: r.key, value: r.value }, '');
}

function activate() {
  const r = ROWS[index];
  if (r.kind === 'action') { send(r.path, { id: r.id }, r.busy); return; }
  if (r.kind === 'field' && r.apply === 'enter') {
    send('/set', { key: r.key, value: r.value }, 'Applying\\u2026');
  }
}

addEventListener('keydown', e => {
  if (e.key === 'ArrowDown') step(1);
  else if (e.key === 'ArrowUp') step(-1);
  else if (e.key === 'ArrowRight') { cycle(1); e.preventDefault(); return; }
  else if (e.key === 'ArrowLeft') { cycle(-1); e.preventDefault(); return; }
  else if (e.key === 'Enter') { activate(); e.preventDefault(); return; }
  else return;
  e.preventDefault();
  render();
});
build();
</script>
"""

VOLUMES = [(str(v), f"{v}%") for v in range(0, 101, 5)]
OVERSCANS = [("0", "None"), ("2", "2%"), ("4", "4%"), ("6", "6%")]
YESNO = [("no", "No"), ("yes", "Yes")]


def model(tune) -> list:
    rows = []

    for screen in tune.displays():
        rows.append({"kind": "header", "text": "Picture",
                     "sub": screen["name"]})
        rows.append({
            "kind": "field", "key": f"mode:{screen['name']}",
            "label": "Size and rate", "apply": "enter",
            "options": [[m["id"], tune.mode_label(m)] for m in screen["modes"]],
            "value": screen["current"],
        })
        rows.append({
            "kind": "field", "key": f"overscan:{screen['name']}",
            "label": "Pull the picture in from the edges", "apply": "enter",
            "options": OVERSCANS, "value": str(screen["overscan"]),
        })
        # One screen. A television has one, and a second would want a whole
        # conversation about which is which that nobody here is having.
        break

    sinks = tune.outputs()
    rows.append({"kind": "header", "text": "Sound",
                 "sub": "Where the sound comes out"})
    if sinks:
        rows.append({
            "kind": "field", "key": "output", "label": "Output",
            "apply": "enter",
            "options": [[s["name"], f"{s['label']} ({s['kind']})"]
                        for s in sinks],
            "value": next((s["name"] for s in sinks if s["current"]),
                          sinks[0]["name"]),
        })
    rows.append({
        "kind": "field", "key": "volume", "label": "Volume", "apply": "now",
        "options": VOLUMES, "value": str(min(range(0, 101, 5),
                                             key=lambda v: abs(v - tune.volume()))),
    })
    rows.append({
        "kind": "field", "key": "mute", "label": "Silence", "apply": "now",
        "options": YESNO, "value": "yes" if tune.muted() else "no",
    })

    rows.append({"kind": "header", "text": "Headphones and remotes",
                 "sub": "Bluetooth devices this television knows"})
    if not tune.bluetooth_ready():
        rows.append({"kind": "action", "id": "", "path": "/noop",
                     "label": "No Bluetooth adapter found"})
        return rows

    for device in tune.devices():
        state = "Connected" if device["connected"] else "Paired"
        rows.append({"kind": "action", "id": device["address"],
                     "path": "/device",
                     "busy": f"Working on {device['name']}…",
                     "label": f"{device['name']} · {state}"})
    rows.append({"kind": "action", "id": "scan", "path": "/scan",
                 "busy": "Searching…",
                 "label": "Search for something to pair"})
    return rows


def run(tune) -> int:
    app = tvui.App("Picture & Sound")

    def render(_query=None):
        return (BODY
                .replace("__NAV__", tvui.NAV_JS)
                .replace("__ROWS__", json.dumps(model(tune))))

    def do_set(payload):
        key = payload.get("key", "")
        value = str(payload.get("value", ""))
        if key.startswith("mode:"):
            if not tune.set_mode(key.split(":", 1)[1], value):
                return {"error": "The screen would not take that size."}
            return {"message": "Picture changed", "rows": model(tune)}
        if key.startswith("overscan:"):
            if not tune.set_overscan(key.split(":", 1)[1], int(value or 0)):
                return {"error": "The screen would not take that."}
            return {"message": "Picture changed"}
        if key == "output":
            if not tune.set_output(value):
                return {"error": "That output would not take the sound."}
            return {"message": "Sound moved", "rows": model(tune)}
        if key == "volume":
            tune.set_volume(int(value or 0))
            return {}
        if key == "mute":
            tune.set_muted(value == "yes")
            return {}
        return {"error": "Nothing to change there."}

    def do_device(payload):
        address = payload.get("id", "")
        known = {d["address"]: d for d in tune.devices(known_only=False)}
        device = known.get(address)
        if device is None:
            return {"error": "That device is no longer there."}
        if device["connected"]:
            tune.disconnect(address)
            return {"message": f"{device['name']} disconnected",
                    "rows": model(tune)}
        if device["paired"]:
            if not tune.connect(address):
                return {"error": f"{device['name']} did not answer."}
            return {"message": f"{device['name']} connected",
                    "rows": model(tune)}
        ok, reason = tune.pair(address)
        if not ok:
            return {"error": f"Could not pair: {reason}"}
        return {"message": f"{device['name']} paired", "rows": model(tune)}

    def do_scan(_payload):
        found = tune.scan()
        rows = model(tune)
        known = {d["address"] for d in tune.devices()}
        nearby = [d for d in found if d["address"] not in known]
        if nearby:
            # Inserted above the search row, so what was just found is where
            # the viewer is already looking.
            extra = [{"kind": "action", "id": d["address"], "path": "/device",
                      "busy": f"Pairing {d['name']}…",
                      "label": f"{d['name']} · Pair"} for d in nearby]
            rows = rows[:-1] + extra + rows[-1:]
        return {"message": f"Found {len(nearby)} new" if nearby
                else "Nothing new found", "rows": rows}

    app.get("/", render)
    app.post("/set", do_set)
    app.post("/device", do_device)
    app.post("/scan", do_scan)
    app.post("/noop", lambda _p: {})
    app.run()
    return 0
