"""The Live TV guide: channels down the side, time across the top.

A grid in the page, walked with the arrow keys. Up and down change channel,
left and right move through time, Enter on a programme that is on now tunes
to it. With no source yet, the same page asks for one instead, with the
page's own keyboard, so the tile is never a dead end.
"""
import datetime as dt
import html
import json
import subprocess
import sys

import tvui

GRID_HOURS = 3
SLOT_MINUTES = 30

GUIDE_BODY = """
<style>
 .guide{margin-top:18px;border-top:2px solid #1C2330}
 .times{display:flex;margin-left:300px;color:var(--dim);font-size:18px;
        height:34px;align-items:center;position:relative}
 .times span{position:absolute}
 .line{display:flex;height:84px;border-bottom:2px solid #1C2330}
 .chan{width:300px;flex:none;display:flex;align-items:center;gap:14px;
       padding:0 14px;font-size:22px;background:#10151D}
 .chan .num{color:var(--accent);min-width:56px;font-weight:600}
 .chan img{width:40px;height:40px;object-fit:contain}
 .shows{position:relative;flex:1;overflow:hidden}
 .show{position:absolute;top:6px;bottom:6px;background:var(--surface);
       border-radius:10px;padding:10px 14px;overflow:hidden;
       border:3px solid transparent;box-sizing:border-box}
 .show.now{background:#1A2230}
 .show.sel{border-color:var(--accent)}
 .show .t{font-size:21px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
 .show .w{font-size:16px;color:var(--dim);margin-top:4px;white-space:nowrap}
 .nowline{position:absolute;top:0;bottom:0;width:3px;background:var(--accent);
          opacity:.8;z-index:2}
 .detail{margin-top:22px;min-height:84px}
 .detail .t{font-size:30px}
 .detail .d{font-size:20px;color:var(--dim);margin-top:6px;max-width:1300px}
 /* "head", not "bar": the shared styles already have a bar, the thin
    progress track the install pages use. */
 .head{display:flex;gap:20px;align-items:center;margin-bottom:6px}
 .pill{background:var(--surface);border-radius:12px;padding:10px 18px;
       font-size:20px;border:3px solid transparent}
 .pill.sel{border-color:var(--accent)}
</style>
<div class="head"><h1 style="margin:0">Live TV</h1>
  <div class="pill" id="sources">Sources</div></div>
<p class="step" id="step">__STEP__</p>
<div class="detail" id="detail"></div>
<div class="guide" id="guide"><div class="times" id="times"></div></div>
<div class="msg" id="msg"></div>
<p class="hint">Up and down for channels, left and right through time. Enter
watches. Up from the top reaches Sources.</p>
<script>
const DATA = __DATA__;
const guideEl = document.getElementById('guide');
const timesEl = document.getElementById('times');
const detail = document.getElementById('detail');
const msg = document.getElementById('msg');
const sourcesPill = document.getElementById('sources');
const START = new Date(DATA.start).getTime();
const END = START + DATA.hours * 3600000;
const VISIBLE_ROWS = 6;
// Not "top": that name belongs to the window, and declaring it at the
// top of a page throws before a single row is drawn.
let row = 0, col = 0, firstRow = 0, onPill = false;

function pct(t) { return (Math.min(Math.max(t, START), END) - START) / (END - START) * 100; }
function clock(t) {
  return new Date(t).toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' });
}

for (let t = START; t < END; t += DATA.slot * 60000) {
  const s = document.createElement('span');
  s.style.left = pct(t) + '%';
  s.textContent = clock(t);
  timesEl.appendChild(s);
}

function showsFor(channel) {
  const list = (channel.shows || []).filter(s => new Date(s.stop).getTime() > START
                                             && new Date(s.start).getTime() < END);
  // A channel with no guide still gets one block, so it can be reached and
  // watched like any other.
  return list.length ? list
    : [{ title: channel.name, start: DATA.start, stop: new Date(END).toISOString(),
         blank: true }];
}

function drawRows() {
  guideEl.querySelectorAll('.line').forEach(el => el.remove());
  const now = Date.now();
  DATA.channels.slice(firstRow, firstRow + VISIBLE_ROWS).forEach((channel, i) => {
    const r = firstRow + i;
    const line = document.createElement('div');
    line.className = 'line';
    const chan = document.createElement('div');
    chan.className = 'chan';
    const num = document.createElement('span');
    num.className = 'num';
    num.textContent = channel.number || '';
    chan.appendChild(num);
    if (channel.logo) {
      const img = document.createElement('img');
      img.src = channel.logo;
      img.onerror = () => img.remove();
      chan.appendChild(img);
    }
    const name = document.createElement('span');
    name.textContent = channel.name;
    chan.appendChild(name);
    const shows = document.createElement('div');
    shows.className = 'shows';
    showsFor(channel).forEach((show, c) => {
      const a = new Date(show.start).getTime(), b = new Date(show.stop).getTime();
      const el = document.createElement('div');
      el.className = 'show' + (a <= now && now < b ? ' now' : '')
                   + (!onPill && r === row && c === col ? ' sel' : '');
      el.style.left = pct(a) + '%';
      el.style.width = `calc(${pct(b) - pct(a)}% - 6px)`;
      const title = document.createElement('div');
      title.className = 't';
      title.textContent = show.title;
      el.appendChild(title);
      if (!show.blank) {
        const when = document.createElement('div');
        when.className = 'w';
        when.textContent = clock(a) + ' \\u2013 ' + clock(b);
        el.appendChild(when);
      }
      shows.appendChild(el);
    });
    if (now >= START && now <= END) {
      const nl = document.createElement('div');
      nl.className = 'nowline';
      nl.style.left = pct(now) + '%';
      shows.appendChild(nl);
    }
    line.append(chan, shows);
    guideEl.appendChild(line);
  });
  sourcesPill.classList.toggle('sel', onPill);
  drawDetail();
}

function drawDetail() {
  detail.innerHTML = '';
  if (onPill || !DATA.channels.length) return;
  const show = showsFor(DATA.channels[row])[col];
  const t = document.createElement('div');
  t.className = 't';
  t.textContent = show.title + (show.subtitle ? ' \\u00b7 ' + show.subtitle : '');
  const d = document.createElement('div');
  d.className = 'd';
  d.textContent = show.blank ? 'No guide for this channel'
    : clock(new Date(show.start).getTime()) + ' \\u2013 '
      + clock(new Date(show.stop).getTime())
      + (show.description ? '  \\u00b7  ' + show.description : '');
  detail.append(t, d);
}

// Moving between channels keeps the same moment in time selected, not the
// same column: the third programme on one channel can be an hour away from the
// third on the next.
function colAt(r, moment) {
  const shows = showsFor(DATA.channels[r]);
  const i = shows.findIndex(s => new Date(s.start).getTime() <= moment
                                 && moment < new Date(s.stop).getTime());
  return i >= 0 ? i : Math.min(col, shows.length - 1);
}

function selectedMoment() {
  const s = showsFor(DATA.channels[row])[col];
  return Math.max(new Date(s.start).getTime(), Math.min(Date.now(), new Date(s.stop).getTime() - 1));
}

function watch() {
  const channel = DATA.channels[row];
  msg.className = 'msg';
  msg.textContent = 'Tuning to ' + (channel.number ? channel.number + ' ' : '') + channel.name + '\\u2026';
  fetch('/watch', { method: 'POST', body: JSON.stringify({ index: row }) });
}

addEventListener('keydown', e => {
  if (!DATA.channels.length) return;
  if (onPill) {
    if (e.key === 'ArrowDown') { onPill = false; }
    else if (e.key === 'Enter') { location.href = '/sources'; return; }
    else return;
  } else if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
    const moment = selectedMoment();
    if (e.key === 'ArrowUp' && row === 0) { onPill = true; }
    else {
      row = Math.min(Math.max(row + (e.key === 'ArrowDown' ? 1 : -1), 0),
                     DATA.channels.length - 1);
      col = colAt(row, moment);
      if (row < firstRow) firstRow = row;
      if (row >= firstRow + VISIBLE_ROWS) firstRow = row - VISIBLE_ROWS + 1;
    }
  } else if (e.key === 'ArrowRight') {
    col = Math.min(col + 1, showsFor(DATA.channels[row]).length - 1);
  } else if (e.key === 'ArrowLeft') {
    col = Math.max(col - 1, 0);
  } else if (e.key === 'Enter') {
    watch(); e.preventDefault(); return;
  } else return;
  e.preventDefault();
  drawRows();
});

row = Math.min(DATA.startRow || 0, Math.max(0, DATA.channels.length - 1));
firstRow = Math.max(0, Math.min(row - 2, DATA.channels.length - VISIBLE_ROWS));
if (DATA.channels.length) col = colAt(row, Date.now());
drawRows();
if (!DATA.channels.length) { onPill = true; sourcesPill.classList.add('sel');
  addEventListener('keydown', e => { if (e.key === 'Enter') location.href = '/sources'; }); }
</script>
"""

SOURCES_BODY = """
<h1>Live TV sources</h1>
<p class="step">Where channels come from. Tunarr is the easiest: its address is
all it needs.</p>
<div class="rows" id="rows"></div>
<div class="msg" id="msg"></div>
<p class="hint">Enter to add or remove. Backspace returns to the guide.</p>
<script>
__NAV__
__KB__
const ITEMS = __ITEMS__;
const rows = document.getElementById('rows');
const msg = document.getElementById('msg');
ITEMS.forEach(it => {
  const el = document.createElement('div');
  el.className = it.kind === 'source' ? 'row' : 'row act';
  const k = document.createElement('div');
  k.className = 'k';
  k.textContent = it.label;
  el.appendChild(k);
  if (it.note) {
    const v = document.createElement('div');
    v.className = 'v';
    v.textContent = it.note;
    el.appendChild(v);
  }
  rows.appendChild(el);
});

function post(path, body) {
  msg.className = 'msg';
  msg.textContent = 'Looking for channels\\u2026';
  fetch(path, { method: 'POST', body: JSON.stringify(body) })
    .then(r => r.json())
    .then(r => {
      if (r.error) { msg.className = 'msg bad'; msg.textContent = r.error; return; }
      msg.textContent = r.message || 'Done';
      setTimeout(() => { location.href = r.go || '/sources'; }, 900);
    });
}

function ask(label, then) {
  tvkeyboard({ label: label, value: '', onDone: v => { if (v.trim()) then(v.trim()); },
               onCancel: () => {} });
}

function choose(i) {
  const it = ITEMS[i];
  if (it.kind === 'source') { post('/remove', { index: it.index }); return; }
  if (it.kind === 'tunarr') {
    ask('Tunarr address, such as tunarr.lan', v => post('/add', { kind: 'tunarr', address: v }));
  } else if (it.kind === 'hdhomerun') {
    ask('HDHomeRun address', v => post('/add', { kind: 'hdhomerun', address: v }));
  } else if (it.kind === 'm3u') {
    ask('Playlist address (M3U)', v =>
      ask('Guide address (XMLTV), or Done to skip', g =>
        post('/add', { kind: 'm3u', playlist: v, guide: g })));
  }
}
const nav = tvnav([...rows.children], choose, () => { location.href = '/'; });
</script>
"""


def run(livetv) -> int:
    app = tvui.App("Live TV")

    def guide_page(_query):
        result = livetv.lineup()
        now = dt.datetime.now(dt.timezone.utc)
        start = now.replace(minute=(now.minute // SLOT_MINUTES) * SLOT_MINUTES,
                            second=0, microsecond=0)
        channels = []
        for channel in result["channels"]:
            channels.append({
                "number": channel.get("number", ""), "name": channel.get("name", ""),
                "logo": channel.get("logo", ""),
                "shows": [{"title": s["title"], "subtitle": s.get("subtitle", ""),
                           "description": s.get("description", ""),
                           "start": s["start"].isoformat(),
                           "stop": s["stop"].isoformat()}
                          for s in channel.get("shows", [])],
            })
        if not livetv.settings()["sources"]:
            step = "No sources yet. Choose Sources to add Tunarr or a tuner."
        elif not channels:
            step = "No channels came back. " + "; ".join(result["errors"][:2])
        else:
            step = f"{len(channels)} channels" + (
                "  ·  " + result["errors"][0] if result["errors"] else "")
        data = {"channels": channels, "start": start.isoformat(),
                "hours": GRID_HOURS, "slot": SLOT_MINUTES,
                "startRow": livetv.start_index(result["channels"]) if channels else 0}
        return (GUIDE_BODY.replace("__STEP__", html.escape(step))
                          .replace("__DATA__", json.dumps(data)))

    def sources_page(_query):
        items = []
        for index, source in enumerate(livetv.settings()["sources"]):
            items.append({"kind": "source", "index": index,
                          "label": source.get("label") or source.get("playlist")
                          or source.get("address"),
                          "note": "Enter removes it"})
        items += [{"kind": "tunarr", "label": "Add Tunarr"},
                  {"kind": "hdhomerun", "label": "Add an HDHomeRun tuner"},
                  {"kind": "m3u", "label": "Add a playlist and guide"}]
        return (SOURCES_BODY.replace("__NAV__", tvui.NAV_JS)
                            .replace("__KB__", tvui.KEYBOARD_JS)
                            .replace("__ITEMS__", json.dumps(items)))

    def do_add(payload):
        kind = payload.get("kind")
        if kind == "tunarr":
            source = livetv.tunarr_source(payload.get("address", ""))
        elif kind == "hdhomerun":
            source = {"kind": "hdhomerun", "label": payload.get("address", ""),
                      "address": livetv.guide.normalise_address(
                          payload.get("address", ""), 80), "guide": ""}
        elif kind == "m3u":
            source = {"kind": "m3u", "label": payload.get("playlist", ""),
                      "playlist": payload.get("playlist", ""),
                      "guide": payload.get("guide", "")}
        else:
            return {"error": "Unknown kind of source."}
        livetv.add_source(source)
        result = livetv.lineup(force=True)
        if not result["channels"]:
            return {"error": "Added, but no channels came back: "
                    + "; ".join(result["errors"][:1])}
        return {"message": f"{len(result['channels'])} channels", "go": "/"}

    def do_remove(payload):
        livetv.remove_source(int(payload.get("index", -1)))
        return {"message": "Removed"}

    state = {"watch": None}

    def do_watch(payload):
        state["watch"] = int(payload.get("index", 0))
        return {"ok": True}

    app.get("/", guide_page)
    app.get("/sources", sources_page)
    app.post("/add", do_add)
    app.post("/remove", do_remove)
    app.post("/watch", do_watch, finish=True)

    # The guide closes while a channel plays and comes back when the guide key
    # is pressed in the player, so moving between the two feels like one app.
    while True:
        state["watch"] = None
        app.run()
        if state["watch"] is None:
            return 0
        channels = livetv.lineup()["channels"]
        if not channels:
            return 0
        position = min(state["watch"], len(channels) - 1)
        command = getattr(livetv, "__file__", "") or "/usr/bin/freetvos-livetv"
        code = subprocess.run([sys.executable, command, "watch",
                               "--index", str(position)]).returncode
        if code != 4:
            return 0
