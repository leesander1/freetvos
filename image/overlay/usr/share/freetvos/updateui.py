"""The on-screen page for updates: the switch, this version, and Check now.

Rows, in the same idiom as Picture & Sound. The checking itself is done by a
root service, which this page asks for by leaving a file for it and then
watches the status file until the answer arrives; so the page never needs a
password, and closing it does not stop a download.
"""
import json
import subprocess

import tvui

BODY = """
<h1>Updates</h1>
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
let watching = null;

function selectable(r) { return r.kind === 'field' || r.kind === 'action'; }

function build() {
  rowsEl.innerHTML = '';
  ROWS.forEach(r => {
    const el = document.createElement('div');
    if (r.kind === 'header') {
      el.className = 'hdr';
      el.innerHTML = '<span></span><span class="sub"></span>';
      el.children[0].textContent = r.text;
      el.children[1].textContent = r.sub || '';
    } else if (r.kind === 'info') {
      el.className = 'row info';
      el.innerHTML = '<div class="k"></div>';
      el.querySelector('.k').textContent = r.label;
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
  if (index >= ROWS.length || !selectable(ROWS[index])) {
    index = ROWS.findIndex(selectable);
  }
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
    el.querySelector('.v').textContent = r.options[optionIndex(r)][1];
    el.querySelector('.arrows').textContent = '\\u2039 \\u203a';
  });
  if (rowsEl.children[index]) {
    rowsEl.children[index].scrollIntoView({ block: 'center' });
  }
}

function step(delta) {
  for (let i = index + delta; i >= 0 && i < ROWS.length; i += delta) {
    if (selectable(ROWS[i])) { index = i; return; }
  }
}

function answer(r) {
  if (r.error) { msg.className = 'msg bad'; msg.textContent = r.error; }
  else if (r.message !== undefined) { msg.className = 'msg'; msg.textContent = r.message; }
  if (r.rows) { ROWS = r.rows; build(); }
  if (r.checking && !watching) watching = setInterval(poll, 3000);
  if (!r.checking && watching) { clearInterval(watching); watching = null; }
}

function send(path, body, note) {
  if (busy) return;
  busy = true;
  if (note) { msg.className = 'msg'; msg.textContent = note; }
  fetch(path, { method: 'POST', body: JSON.stringify(body) })
    .then(r => r.json())
    .then(r => { busy = false; answer(r); })
    .catch(() => { busy = false; });
}

function poll() {
  fetch('/rows', { method: 'POST', body: '{}' })
    .then(r => r.json()).then(answer).catch(() => {});
}

function cycle(delta) {
  const r = ROWS[index];
  if (!r || r.kind !== 'field') return;
  const n = r.options.length;
  r.value = r.options[(optionIndex(r) + delta + n) % n][0];
  render();
  send('/set', { key: r.key, value: r.value }, '');
}

function activate() {
  const r = ROWS[index];
  if (r && r.kind === 'action') send(r.path, {}, r.busy);
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
answer({ checking: __CHECKING__ });
</script>
<style>
  .row.info { background: none; border-color: transparent; padding-left: 0; }
  .row.info .k { color: var(--dim); }
</style>
"""

ONOFF = [["on", "On"], ["off", "Off"]]


def current(update) -> dict:
    """The status file, counting a check asked for but not yet begun."""
    state = dict(update.read_status())
    if update.check_pending():
        state["checking"] = True
    return state


def model(update) -> list:
    state = current(update)
    rows = [
        {"kind": "header", "text": "Automatic updates",
         "sub": "New versions download by themselves. The TV restarts to "
                "finish between 2 and 5:30 in the morning, never while "
                "something is playing."},
        {"kind": "field", "key": "automatic", "label": "Update automatically",
         "options": ONOFF, "value": "on" if update.enabled() else "off"},
        {"kind": "header", "text": "This television"},
        {"kind": "info", "label": update.version_line(state)},
        {"kind": "info", "label": update.status_line(state)},
    ]
    if state.get("checking") and state.get("detail"):
        rows.append({"kind": "info", "label": state["detail"]})
    if not state.get("checking"):
        rows.append({"kind": "action", "path": "/check",
                     "busy": "Asking for an update…",
                     "label": "Check for an update now"})
    if state.get("staged"):
        rows.append({"kind": "action", "path": "/restart",
                     "busy": "Restarting…",
                     "label": "Restart now to finish the update"})
    return rows


def reply(update, **extra) -> dict:
    return {"rows": model(update),
            "checking": bool(current(update).get("checking")), **extra}


def run(update) -> int:
    app = tvui.App("Updates")

    def render(_query=None):
        return (BODY
                .replace("__NAV__", tvui.NAV_JS)
                .replace("__ROWS__", json.dumps(model(update)))
                .replace("__CHECKING__",
                         json.dumps(bool(current(update).get("checking")))))

    def do_set(payload):
        if payload.get("key") != "automatic":
            return {"error": "Nothing to change there."}
        on = payload.get("value") == "on"
        update.set_enabled(on)
        return reply(update, message="Automatic updates are on" if on
                     else "Automatic updates are off. Check now still works.")

    def do_check(_payload):
        try:
            update.request_check()
        except OSError as e:
            return {"error": f"Could not ask for a check: {e}"}
        return reply(update, message="")

    def do_restart(_payload):
        subprocess.Popen(["systemctl", "reboot"])
        return {"message": "Restarting…"}

    app.get("/", render)
    app.post("/set", do_set)
    app.post("/check", do_check)
    app.post("/restart", do_restart)
    app.post("/rows", lambda _p: reply(update))
    app.run()
    return 0
