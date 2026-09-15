"""The Meetings page: join a Zoom, Meet or Teams call with a remote.

Pick the service, type the meeting ID and passcode from the invitation with the
page's own keyboard, and join. Or paste a whole invitation link. The page also
says which cameras and microphones it can see, because a call with no camera
fails inside the service's own page, where the reason is hard to read from a
sofa.
"""
import json

import tvui

BODY = """
<h1>Meetings</h1>
<p class="step" id="step">__DEVICES__</p>
<div class="rows" id="rows"></div>
<div class="msg" id="msg"></div>
<p class="hint">Enter on a line to type in it. Back leaves.</p>
<style>
 .hdr{font-size:28px;margin:30px 0 4px}
 .hdr:first-child{margin-top:0}
 .row .tag{color:var(--accent)}
</style>
<script>
__NAV__
__KB__
const SERVICES = [
  { id: 'zoom', name: 'Zoom', fields: [['meeting', 'Meeting ID'], ['passcode', 'Passcode, if the invitation has one']] },
  { id: 'meet', name: 'Google Meet', fields: [['meeting', 'Meeting code, such as abc-defg-hij']] },
  { id: 'teams', name: 'Microsoft Teams', fields: [['meeting', 'Meeting ID'], ['passcode', 'Passcode']] },
];
const values = { zoom: {}, meet: {}, teams: {}, link: '' };
const rows = document.getElementById('rows');
const msg = document.getElementById('msg');
let nav = null;

function items() {
  const out = [];
  SERVICES.forEach(s => {
    out.push({ kind: 'header', text: s.name });
    s.fields.forEach(f => out.push({ kind: 'field', service: s.id, key: f[0], label: f[1] }));
    out.push({ kind: 'join', service: s.id, label: 'Join ' + s.name });
  });
  out.push({ kind: 'header', text: 'An invitation link' });
  out.push({ kind: 'link', label: 'Paste or type the link' });
  out.push({ kind: 'join-link', label: 'Join from the link' });
  return out;
}

function draw(at) {
  rows.innerHTML = '';
  const cells = [];
  items().forEach(it => {
    const el = document.createElement('div');
    if (it.kind === 'header') {
      el.className = 'hdr'; el.textContent = it.text; rows.appendChild(el); return;
    }
    el.className = it.kind.startsWith('join') ? 'row act' : 'row';
    const k = document.createElement('div'); k.className = 'k'; k.textContent = it.label;
    el.appendChild(k);
    if (it.kind === 'field' || it.kind === 'link') {
      const v = document.createElement('div'); v.className = 'v';
      const value = it.kind === 'link' ? values.link : (values[it.service][it.key] || '');
      v.textContent = value || 'Not set';
      el.appendChild(v);
    }
    rows.appendChild(el);
    cells.push({ el: el, it: it });
  });
  nav = tvnav(cells.map(c => c.el), i => choose(cells[i].it), null, at || 0);
  draw.cells = cells;
}

function join(body) {
  msg.className = 'msg';
  msg.textContent = 'Joining\\u2026';
  fetch('/join', { method: 'POST', body: JSON.stringify(body) })
    .then(r => r.json())
    .then(r => {
      if (r.error) { msg.className = 'msg bad'; msg.textContent = r.error; return; }
      msg.textContent = 'Opening ' + r.name + '\\u2026';
    });
}

function choose(it) {
  const at = nav.current();
  if (it.kind === 'field' || it.kind === 'link') {
    const current = it.kind === 'link' ? values.link : (values[it.service][it.key] || '');
    tvkeyboard({ label: it.label, value: current,
      onDone: v => {
        if (it.kind === 'link') values.link = v.trim();
        else values[it.service][it.key] = v.trim();
        draw(Math.min(at + 1, draw.cells.length - 1));
      },
      onCancel: () => draw(at) });
    return;
  }
  if (it.kind === 'join') {
    join({ service: it.service, meeting: values[it.service].meeting || '',
           passcode: values[it.service].passcode || '' });
  } else if (it.kind === 'join-link') {
    join({ link: values.link });
  }
}

draw(0);
</script>
"""


def run(meet) -> int:
    app = tvui.App("Meetings")

    def page(_query):
        found = meet.cameras()
        mics = meet.microphones()
        if found:
            devices = f"Camera: {found[0]}" + (
                f"  ·  Microphone: {mics[0]}" if mics else "  ·  No microphone")
        else:
            devices = ("No camera connected. You can still join and listen; "
                       "plug in a USB webcam to be seen.")
        return (BODY.replace("__NAV__", tvui.NAV_JS)
                    .replace("__KB__", tvui.KEYBOARD_JS)
                    .replace("__DEVICES__", devices))

    chosen: dict = {}

    def do_join(payload):
        try:
            if payload.get("link"):
                service, url = meet.from_invite(payload["link"])
            else:
                service = payload.get("service", "")
                url = meet.join_url(service, payload.get("meeting", ""),
                                    payload.get("passcode", ""))
        except ValueError as exc:
            return {"error": str(exc)}
        chosen.update(service=service, url=url)
        return {"name": meet.SERVICES[service]["name"]}

    app.get("/", page)
    app.post("/join", do_join, finish=True)
    app.run()
    if chosen.get("url"):
        return meet.open_call(chosen["service"], chosen["url"])
    return 0
