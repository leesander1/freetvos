"""The page shown when game streaming is asked for and is not installed yet.

One question and then a progress report. The download is most of a gigabyte and
takes minutes, so the page keeps saying what it is doing; a television showing
nothing for minutes is a television somebody reboots half way through.
"""
import threading

import tvui

BODY = """
<h1>Game streaming</h1>
<p class="step" id="step">Moonlight streams a game from a PC in the house.</p>
<div class="rows">
  <div class="row act sel" id="go"><div class="k">Install it</div></div>
</div>
<p class="note" id="note">Around two and a half gigabytes the first time. Nearly
all of that is the runtime underneath it, which anything else installed this way
afterwards will share. It stays installed.</p>
<div class="msg" id="msg"></div>
<p class="hint">Enter installs. Back leaves.</p>
<style>
 .note{font-size:22px;color:var(--dim);max-width:880px;line-height:1.5;
       margin-top:28px}
 .log{font-size:20px;color:var(--dim);margin-top:18px;
      font-family:ui-monospace,monospace}
</style>
<script>
let started = false;
const msg = document.getElementById('msg');
const note = document.getElementById('note');
const go = document.getElementById('go');

function poll() {
  fetch('/progress', { method: 'POST', body: '{}' })
    .then(r => r.json())
    .then(r => {
      if (r.line) { msg.className = 'msg'; msg.textContent = r.line; }
      if (r.done) {
        msg.textContent = 'Installed. Opening\\u2026';
        fetch('/launch', { method: 'POST', body: '{}' });
        return;
      }
      if (r.failed) {
        msg.className = 'msg bad';
        msg.textContent = r.line || 'The install did not finish.';
        started = false;
        go.querySelector('.k').textContent = 'Try again';
        return;
      }
      setTimeout(poll, 1500);
    })
    .catch(() => setTimeout(poll, 3000));
}

addEventListener('keydown', e => {
  if (e.key === 'Enter' && !started) {
    started = true;
    go.querySelector('.k').textContent = 'Installing\\u2026';
    note.textContent = 'This takes a few minutes. Leaving this page stops it.';
    fetch('/install', { method: 'POST', body: '{}' });
    setTimeout(poll, 1200);
    e.preventDefault();
  } else if (e.key === 'Backspace') {
    location.href = 'about:blank';
  }
});
</script>
"""


def run(moonlight) -> int:
    app = tvui.App("Game streaming")
    state = {"line": "", "done": False, "failed": False, "running": False}
    result = {"launch": False}

    def worker():
        def note(line):
            state["line"] = line[:120]
        ok = moonlight.install(on_line=note)
        state["done"] = ok
        state["failed"] = not ok
        state["running"] = False

    def do_install(_payload):
        if state["running"]:
            return {"ok": True}
        state.update({"running": True, "done": False, "failed": False,
                      "line": "Asking Flathub…"})
        threading.Thread(target=worker, daemon=True).start()
        return {"ok": True}

    def do_progress(_payload):
        return {"line": state["line"], "done": state["done"],
                "failed": state["failed"]}

    def do_launch(_payload):
        result["launch"] = True
        return {"ok": True}

    app.get("/", lambda _q: BODY)
    app.post("/install", do_install)
    app.post("/progress", do_progress)
    app.post("/launch", do_launch, finish=True)
    app.run()

    if result["launch"] and moonlight.installed():
        return moonlight.launch()
    return 0
