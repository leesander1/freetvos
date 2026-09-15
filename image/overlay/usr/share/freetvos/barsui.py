"""The settings page for the bars along the bottom of the screen.

One section per bar, in stacking order. Left and right change a value, Enter
types into a text setting with the page's own keyboard, and each section has a
row to move its bar up or down the stack.
"""
import json

import tvui

WHEN = {
    "stocks": [("always", "Always"), ("market", "While the market is open"),
               ("window", "At set hours")],
    "sports": [("always", "Always"), ("live", "While games are live"),
               ("window", "At set hours")],
    "custom": [("always", "Always"), ("window", "At set hours")],
}

DAYS = [("", "Every day"), ("mon,tue,wed,thu,fri", "Weekdays"),
        ("sat,sun", "Weekends")]

WINDOWS = [("06:00-09:00", "6 to 9 in the morning"),
           ("09:30-16:00", "9:30 to 4"), ("17:00-23:00", "5 to 11 in the evening"),
           ("18:00-02:00", "6 in the evening to 2 in the morning")]

SPEEDS = [("80", "Slow"), ("140", "Normal"), ("220", "Fast")]

NAMES = {"stocks": "Stock prices", "sports": "Live scores",
         "custom": "Your own bar"}

BODY = """
<h1>Tickers</h1>
<p class="step">Bars along the bottom of the screen, stacked in this order.</p>
<div class="rows" id="rows"></div>
<div class="msg" id="msg"></div>
<p class="hint">Up and down to move. Left and right to change. Enter to type
or to act. Back leaves; changes are saved as you make them.</p>
<style>
 .hdr{font-size:28px;margin:34px 0 4px}
 .hdr:first-child{margin-top:0}
 .hdr .sub{display:block;font-size:18px;color:var(--dim);margin-top:4px}
</style>
<script>
__NAV__
__KB__
let ROWS = __ROWS__;
const rows = document.getElementById('rows');
const msg = document.getElementById('msg');
let nav = null;

function draw(at) {
  rows.innerHTML = '';
  const cells = [];
  ROWS.forEach(r => {
    const el = document.createElement('div');
    if (r.kind === 'header') {
      el.className = 'hdr';
      el.textContent = r.text;
      if (r.sub) {
        const s = document.createElement('span');
        s.className = 'sub';
        s.textContent = r.sub;
        el.appendChild(s);
      }
      rows.appendChild(el);
      return;
    }
    el.className = r.kind === 'action' ? 'row act' : 'row';
    const k = document.createElement('div');
    k.className = 'k';
    k.textContent = r.label;
    el.appendChild(k);
    if (r.kind !== 'action') {
      const v = document.createElement('div');
      v.className = 'v';
      v.textContent = r.kind === 'text' ? (r.value || 'Not set')
                    : (r.options.find(o => o[0] === r.value) || r.options[0])[1];
      el.appendChild(v);
    }
    rows.appendChild(el);
    cells.push(el);
    el.dataset.row = ROWS.indexOf(r);
  });
  nav = tvnav(cells, choose, () => history.back(), at || 0);
  return cells;
}

function rowFor(cellIndex) {
  const cells = [...rows.querySelectorAll('.row')];
  return ROWS[Number(cells[cellIndex].dataset.row)];
}

function send(change) {
  const at = nav ? nav.current() : 0;
  return fetch('/change', { method: 'POST', body: JSON.stringify(change) })
    .then(r => r.json())
    .then(r => {
      if (r.error) { msg.className = 'msg bad'; msg.textContent = r.error; return; }
      ROWS = r.rows;
      msg.className = 'msg';
      msg.textContent = r.message || 'Saved';
      draw(r.focus !== undefined ? r.focus : at);
    });
}

function cycle(delta) {
  const r = rowFor(nav.current());
  if (r.kind !== 'choice') return;
  const i = Math.max(0, r.options.findIndex(o => o[0] === r.value));
  const next = r.options[(i + delta + r.options.length) % r.options.length][0];
  send({ bar: r.bar, key: r.key, value: next });
}

function choose(i) {
  const r = rowFor(i);
  if (r.kind === 'action' && r.action === 'stocks') { location.href = '/stocks'; return; }
  if (r.kind === 'choice') { cycle(1); return; }
  if (r.kind === 'action') { send({ bar: r.bar, action: r.action }); return; }
  tvkeyboard({
    label: r.label,
    value: r.value || '',
    onDone: v => send({ bar: r.bar, key: r.key, value: v.trim() }),
    onCancel: () => draw(nav.current()),
  });
}

draw(0);
// Left and right change a choice. Registered after the navigation's own
// handler so this one sees the key first and can claim it.
addEventListener('keydown', e => {
  if (document.querySelector('.kb')) return;
  if (e.key !== 'ArrowLeft' && e.key !== 'ArrowRight') return;
  const r = rowFor(nav.current());
  if (r.kind !== 'choice') return;
  e.preventDefault();
  e.stopImmediatePropagation();
  cycle(e.key === 'ArrowRight' ? 1 : -1);
}, true);
</script>
"""


# One press to add the symbols most people watch. Indexes as the funds that
# track them, because that is what trades while the market is open.
POPULAR = [
    ("SPY", "S&P 500", "etf"), ("QQQ", "Nasdaq 100", "etf"),
    ("DIA", "Dow Jones", "etf"), ("IWM", "Russell 2000", "etf"),
    ("AAPL", "Apple", "stocks"), ("MSFT", "Microsoft", "stocks"),
    ("NVDA", "NVIDIA", "stocks"), ("AMZN", "Amazon", "stocks"),
    ("GOOGL", "Alphabet", "stocks"), ("META", "Meta", "stocks"),
    ("TSLA", "Tesla", "stocks"), ("BRK.B", "Berkshire Hathaway", "stocks"),
    ("JPM", "JPMorgan Chase", "stocks"), ("GLD", "Gold", "etf"),
]

STOCKS_BODY = """
<style>
 .hdr{font-size:28px;margin:30px 0 4px}
 .hdr:first-child{margin-top:0}
 .hdr .sub{display:block;font-size:18px;color:var(--dim);margin-top:4px}
 /* The same size as every other row's text. Without it a symbol and its
    company rendered at the browser's default, half the size of the rows on
    the Tickers page, which is unreadable across a room. */
 .row .sym{font-size:24px;font-weight:600;min-width:140px}
 .row .nm{flex:1;font-size:22px;color:var(--dim)}
 .row .tag{font-size:22px;color:var(--accent)}
</style>
<h1>Stocks on the ticker</h1>
<p class="step">They scroll past in this order.</p>
<div class="rows" id="rows"></div>
<div class="msg" id="msg"></div>
<p class="hint">Enter adds or removes. Left and right move a chosen stock
earlier or later. Back returns to Tickers.</p>
<script>
__NAV__
__KB__
let STATE = __STATE__;
const rows = document.getElementById('rows');
const msg = document.getElementById('msg');
let nav = null;

function items() {
  const out = [];
  out.push({ kind: 'header', text: 'Chosen',
             sub: STATE.chosen.length ? '' : 'Nothing yet. Search, or pick from below.' });
  STATE.chosen.forEach((c, i) => out.push({ kind: 'chosen', symbol: c.symbol,
                                            name: c.name, index: i }));
  out.push({ kind: 'search', label: 'Search by company or symbol' });
  if (STATE.results) {
    out.push({ kind: 'header', text: 'Results for \u201c' + STATE.query + '\u201d',
               sub: STATE.results.length ? '' : 'Nothing found' });
    STATE.results.forEach(r => out.push({ kind: 'option', symbol: r.symbol,
                                          name: r.name, asset: r.asset }));
  }
  out.push({ kind: 'header', text: 'Popular' });
  STATE.popular.forEach(p => out.push({ kind: 'option', symbol: p.symbol,
                                        name: p.name, asset: p.asset }));
  return out;
}

function chosenSet() { return new Set(STATE.chosen.map(c => c.symbol)); }

function draw(focusKey) {
  rows.innerHTML = '';
  const cells = [];
  const list = items();
  let at = 0;
  const have = chosenSet();
  list.forEach(it => {
    const el = document.createElement('div');
    if (it.kind === 'header') {
      el.className = 'hdr';
      el.textContent = it.text;
      if (it.sub) { const s = document.createElement('span'); s.className = 'sub';
                    s.textContent = it.sub; el.appendChild(s); }
      rows.appendChild(el);
      return;
    }
    el.className = it.kind === 'search' ? 'row act' : 'row';
    if (it.kind === 'search') {
      const k = document.createElement('div'); k.className = 'k';
      k.textContent = it.label; el.appendChild(k);
    } else {
      const sym = document.createElement('div'); sym.className = 'sym';
      sym.textContent = it.symbol;
      const nm = document.createElement('div'); nm.className = 'nm';
      nm.textContent = it.name || '';
      const tag = document.createElement('div'); tag.className = 'tag';
      tag.textContent = it.kind === 'chosen' ? (it.index + 1) + ' \u2039 \u203a'
                      : (have.has(it.symbol) ? '\u2713 On the ticker' : 'Add');
      el.append(sym, nm, tag);
    }
    const key = it.kind + ':' + (it.symbol || it.kind);
    if (key === focusKey) at = cells.length;
    el.dataset.key = key;
    rows.appendChild(el);
    cells.push({ el: el, it: it });
  });
  nav = tvnav(cells.map(c => c.el), i => choose(cells[i].it), () => { location.href = '/'; }, at);
  draw.cells = cells;
}

function save(focusKey) {
  return fetch('/stocks/save', { method: 'POST', body: JSON.stringify({ chosen: STATE.chosen }) })
    .then(r => r.json())
    .then(r => {
      if (r.error) { msg.className = 'msg bad'; msg.textContent = r.error; return; }
      msg.className = 'msg'; msg.textContent = r.message || 'Saved';
      draw(focusKey);
    });
}

function choose(it) {
  if (it.kind === 'search') {
    tvkeyboard({ label: 'Company or symbol', value: STATE.query || '',
      onDone: v => {
        if (!v.trim()) { draw('search:search'); return; }
        msg.className = 'msg'; msg.textContent = 'Searching\u2026';
        fetch('/stocks/search', { method: 'POST', body: JSON.stringify({ query: v.trim() }) })
          .then(r => r.json())
          .then(r => {
            if (r.error) { msg.className = 'msg bad'; msg.textContent = r.error; return; }
            msg.textContent = '';
            STATE.query = v.trim(); STATE.results = r.results;
            draw(r.results.length ? 'option:' + r.results[0].symbol : 'search:search');
          });
      },
      onCancel: () => draw('search:search') });
    return;
  }
  const have = chosenSet();
  if (it.kind === 'chosen') {
    STATE.chosen.splice(it.index, 1);
    const next = STATE.chosen[Math.min(it.index, STATE.chosen.length - 1)];
    save(next ? 'chosen:' + next.symbol : 'search:search');
    return;
  }
  if (have.has(it.symbol)) {
    STATE.chosen = STATE.chosen.filter(c => c.symbol !== it.symbol);
  } else {
    STATE.chosen.push({ symbol: it.symbol, name: it.name, asset: it.asset });
  }
  save('option:' + it.symbol);
}

draw();
// Left and right reorder a chosen stock. Taken before the navigation sees them,
// so they move the stock rather than the highlight.
addEventListener('keydown', e => {
  if (document.querySelector('.kb')) return;
  if (e.key !== 'ArrowLeft' && e.key !== 'ArrowRight') return;
  const cell = draw.cells[nav.current()];
  if (!cell || cell.it.kind !== 'chosen') return;
  e.preventDefault(); e.stopImmediatePropagation();
  const i = cell.it.index, j = i + (e.key === 'ArrowRight' ? 1 : -1);
  if (j < 0 || j >= STATE.chosen.length) return;
  const moved = STATE.chosen.splice(i, 1)[0];
  STATE.chosen.splice(j, 0, moved);
  save('chosen:' + moved.symbol);
}, true);
</script>
"""


def stocks_state(bars_module) -> dict:
    bar = next(b for b in bars_module.settings()["bars"] if b["id"] == "stocks")
    names = {s: n for s, n, _ in POPULAR}
    names.update(bar.get("names") or {})
    assets = bar.get("assets") or {}
    return {
        "chosen": [{"symbol": s, "name": names.get(s, ""),
                    "asset": assets.get(s, "")} for s in bar.get("symbols") or []],
        "popular": [{"symbol": s, "name": n, "asset": a} for s, n, a in POPULAR],
        "results": None, "query": "",
    }


def save_stocks(bars_module, chosen: list) -> str:
    symbols = [c.get("symbol", "") for c in chosen]
    assets = {c["symbol"]: c["asset"] for c in chosen if c.get("asset")}
    names = {c["symbol"]: c["name"] for c in chosen if c.get("name")}
    bars_module.set_stocks(symbols, assets)
    bars_module.update_bar("stocks", names=names)
    count = len([s for s in symbols if s])
    return f"{count} on the ticker" if count else "Ticker is empty"


def rows_for(bars_module) -> list:
    data = bars_module.settings()
    notes = {}
    try:
        notes = bars_module.build(data, bars_module.Feeder(),
                                  bars_module.dt.datetime.now().astimezone())["notes"]
    except Exception:                                       # noqa: BLE001
        pass

    rows = []
    for position, bar in enumerate(data["bars"]):
        kind = bar["id"]
        status = notes.get(kind, "")
        rows.append({"kind": "header", "text": NAMES[kind],
                     "sub": "Showing now" if status == "showing"
                     else ("Off" if status == "off" else status.capitalize())})
        rows.append({"kind": "choice", "bar": kind, "key": "enabled",
                     "label": "Show this bar",
                     "options": [["no", "No"], ["yes", "Yes"]],
                     "value": "yes" if bar["enabled"] else "no"})
        rows.append({"kind": "choice", "bar": kind, "key": "when",
                     "label": "When", "options": [list(o) for o in WHEN[kind]],
                     "value": bar["when"]})
        if bar["when"] == "window":
            options = [list(o) for o in WINDOWS]
            if bar.get("window") and bar["window"] not in dict(WINDOWS):
                options.insert(0, [bar["window"], bar["window"]])
            rows.append({"kind": "choice", "bar": kind, "key": "window",
                         "label": "Hours", "options": options,
                         "value": bar.get("window") or WINDOWS[1][0]})
        rows.append({"kind": "choice", "bar": kind, "key": "days",
                     "label": "Days", "options": [list(o) for o in DAYS],
                     "value": ",".join(bar.get("days") or [])})
        if kind == "stocks":
            chosen = bar.get("symbols") or []
            rows.append({"kind": "action", "bar": kind, "action": "stocks",
                         "label": "Choose stocks: " + (
                             ", ".join(chosen[:5]) + (
                                 f" and {len(chosen) - 5} more"
                                 if len(chosen) > 5 else "")
                             if chosen else "none yet")})
        if kind == "sports":
            rows.append({"kind": "choice", "bar": kind, "key": "followed_only",
                         "label": "Games",
                         "options": [["no", "Every game in my leagues"],
                                     ["yes", "Only teams I follow"]],
                         "value": "yes" if bar.get("followed_only") else "no"})
        if kind == "custom":
            rows.append({"kind": "text", "bar": kind, "key": "title",
                         "label": "Title", "value": bar.get("title", "")})
            rows.append({"kind": "text", "bar": kind, "key": "message",
                         "label": "Message", "value": bar.get("message", "")})
            rows.append({"kind": "text", "bar": kind, "key": "logo",
                         "label": "Logo, a web address or a file",
                         "value": bar.get("logo", "")})
            rows.append({"kind": "text", "bar": kind, "key": "feed",
                         "label": "News feed address (RSS, Atom or JSON Feed)",
                         "value": bar.get("feed", "")})
        rows.append({"kind": "choice", "bar": kind, "key": "speed",
                     "label": "Speed", "options": [list(o) for o in SPEEDS],
                     "value": str(bar.get("speed", 140))})
        if position > 0:
            rows.append({"kind": "action", "bar": kind, "action": "up",
                         "label": "Move this bar up"})
        if position < len(data["bars"]) - 1:
            rows.append({"kind": "action", "bar": kind, "action": "down",
                         "label": "Move this bar down"})
    return rows


def apply(bars_module, change: dict) -> str:
    kind = change.get("bar")
    if kind not in bars_module.KINDS:
        raise ValueError("That bar does not exist.")
    if change.get("action") in ("up", "down"):
        bars_module.move_bar(kind, -1 if change["action"] == "up" else 1)
        return "Moved " + ("up" if change["action"] == "up" else "down")

    key, value = change.get("key"), change.get("value", "")
    if key in ("enabled", "followed_only"):
        bars_module.update_bar(kind, **{key: value == "yes"})
    elif key == "days":
        bars_module.update_bar(kind, days=[d for d in value.split(",") if d])
    elif key == "speed":
        bars_module.update_bar(kind, speed=int(value) if value.isdigit() else 140)
    elif key == "symbols":
        symbols = [s.strip().upper() for s in value.replace(",", " ").split()
                   if s.strip()]
        current = next(b for b in bars_module.settings()["bars"]
                       if b["id"] == "stocks")
        bars_module.set_stocks(symbols, current.get("assets") or {})
    elif key == "when":
        changes = {"when": value}
        current = next(b for b in bars_module.settings()["bars"]
                       if b["id"] == kind)
        if value == "window" and not current.get("window"):
            changes["window"] = WINDOWS[1][0]
        bars_module.update_bar(kind, **changes)
    elif key in ("window", "title", "message", "logo", "feed"):
        bars_module.update_bar(kind, **{key: value})
    else:
        raise ValueError("That setting does not exist.")
    return "Saved"


def run(bars_module) -> int:
    app = tvui.App("Tickers")

    def page(_query):
        return (BODY.replace("__NAV__", tvui.NAV_JS)
                    .replace("__KB__", tvui.KEYBOARD_JS)
                    .replace("__ROWS__", json.dumps(rows_for(bars_module))))

    def do_change(payload):
        try:
            message = apply(bars_module, payload)
        except ValueError as exc:
            return {"error": str(exc)}
        rows = rows_for(bars_module)
        result = {"rows": rows, "message": message}
        # After a move the bar's rows are somewhere else; follow them there so
        # pressing Move up twice moves it twice.
        if payload.get("action"):
            focusable = [r for r in rows if r["kind"] != "header"]
            for i, r in enumerate(focusable):
                if r.get("bar") == payload["bar"] and r.get("action"):
                    result["focus"] = i
                    break
        return result

    def stocks_page(_query):
        return (STOCKS_BODY.replace("__NAV__", tvui.NAV_JS)
                           .replace("__KB__", tvui.KEYBOARD_JS)
                           .replace("__STATE__",
                                    json.dumps(stocks_state(bars_module))))

    def do_stocks_save(payload):
        return {"message": save_stocks(bars_module, payload.get("chosen") or [])}

    def do_stocks_search(payload):
        try:
            results = bars_module.sources.search_symbols(payload.get("query", ""))
        except bars_module.sources.SourceError as exc:
            return {"error": f"Search is not reachable: {exc}"}
        return {"results": results}

    app.get("/", page)
    app.get("/stocks", stocks_page)
    app.post("/stocks/save", do_stocks_save)
    app.post("/stocks/search", do_stocks_search)
    app.post("/change", do_change)
    app.run()
    return 0
