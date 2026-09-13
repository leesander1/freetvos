"""The on-screen pages for scores.

A grid of cards that refreshes itself. A score that needs a button press to
update is not a score, and somebody watching a close game will not press it.
"""
import html
import json

import tvui

TODAY_BODY = """
<h1>Scores</h1>
<p class="step" id="step">__STEP__</p>
<div class="grid" id="grid"></div>
<p class="empty" id="empty" hidden>Nothing on in the leagues you follow.</p>
<div class="msg" id="msg"></div>
<p class="hint">Enter opens a game. Back leaves.</p>
<style>.empty{font-size:24px;color:var(--dim)}</style>
<script>
__NAV__
let GAMES = __GAMES__;
const grid = document.getElementById('grid');
const msg = document.getElementById('msg');
// Past the two settings cards, onto the first score.
let index = __START__;
let nav = null;

function esc(s) {
  const d = document.createElement('div');
  d.textContent = s == null ? '' : s;
  return d.innerHTML;
}

function side(t, state, other) {
  const lost = state === 'post' && !t.winner && other.winner;
  return '<div class="team' + (lost ? ' lost' : '') + '">'
    + (t.logo ? '<img src="' + esc(t.logo) + '" alt="">'
              : '<span style="width:42px"></span>')
    + '<span class="rk">' + (t.rank ? esc(t.rank) : '') + '</span>'
    + '<span class="ab">' + esc(t.abbr) + '</span>'
    + '<span class="rec">' + esc(t.record) + '</span>'
    + '<span class="sc">' + esc(t.score) + '</span></div>';
}

function cardHtml(g) {
  const top = esc(g.league_name) + (g.network ? ' \\u00b7 ' + esc(g.network) : '');
  return '<div class="top">' + (g.followed ? '<span class="star">\\u2605</span>' : '')
       + '<span>' + top + '</span></div>'
       + side(g.away, g.state, g.home)
       + side(g.home, g.state, g.away)
       + '<div class="foot">' + esc(g.detail) + '</div>'
       + (g.situation ? '<div class="sit">' + esc(g.situation) + '</div>' : '');
}

function build() {
  grid.innerHTML = '';
  GAMES.forEach(g => {
    const el = document.createElement('div');
    el.className = 'card' + (g.state === 'in' ? ' live' : '');
    el.innerHTML = g.action ? '' : cardHtml(g);
    if (g.action) { el.className = 'card action'; el.textContent = g.label; }
    grid.appendChild(el);
  });
  document.getElementById('empty').hidden = GAMES.length > 2;
  const cells = [...grid.children];
  if (index >= cells.length) index = Math.max(0, cells.length - 1);
  nav = tvnav(cells, choose, null, index);
}

function choose(i) {
  const g = GAMES[i];
  index = i;
  if (g.go) { location.href = g.go; return; }
}

// Refreshed on a timer rather than on a keypress. The highlight is kept on the
// same game rather than in the same place: games re-sort as they start and
// finish, so holding the position would move the highlight onto whatever had
// taken that slot, which it did.
function refresh() {
  fetch('/data', { method: 'POST', body: '{}' })
    .then(r => r.json())
    .then(r => {
      if (r.games) {
        const at = nav ? nav.current() : index;
        const was = GAMES[at] && GAMES[at].id;
        GAMES = r.games;
        const again = was ? GAMES.findIndex(g => g.id === was) : -1;
        index = again >= 0 ? again : Math.min(at, GAMES.length - 1);
        build();
        msg.textContent = '';
      }
      if (r.error) { msg.className = 'msg bad'; msg.textContent = r.error; }
      setTimeout(refresh, 25000);
    })
    .catch(() => setTimeout(refresh, 40000));
}

build();
setTimeout(refresh, 25000);
</script>
"""

GAME_BODY = """
<h1>__TITLE__</h1>
<p class="step">__SUB__</p>
<div class="rows" id="rows">
  <div class="card" style="width:640px">__CARD__</div>
</div>
<p class="detail" id="detail">__DETAIL__</p>
<div class="rows" id="acts"></div>
<div class="msg" id="msg"></div>
<p class="hint">Backspace goes back.</p>
<style>
 .detail{font-size:22px;color:var(--dim);max-width:900px;line-height:1.5;
         margin-top:24px;white-space:pre-line}
</style>
<script>
__NAV__
const ACTS = __ACTS__;
const acts = document.getElementById('acts');
const msg = document.getElementById('msg');
ACTS.forEach(a => {
  const el = document.createElement('div');
  el.className = 'row act';
  el.innerHTML = '<div class="k"></div>';
  el.querySelector('.k').textContent = a.label;
  acts.appendChild(el);
});
const cells = [...acts.children];
function choose(i) {
  const a = ACTS[i];
  msg.className = 'msg';
  msg.textContent = 'Saving\\u2026';
  fetch('/follow-team', { method: 'POST', body: JSON.stringify(a) })
    .then(r => r.json())
    .then(r => {
      if (r.error) { msg.className = 'msg bad'; msg.textContent = r.error; }
      else { ACTS[i].label = r.label; cells[i].querySelector('.k').textContent = r.label;
             msg.textContent = r.message || ''; }
    });
}
if (cells.length) tvnav(cells, choose, () => history.back());
else addEventListener('keydown', e => {
  if (e.key === 'Backspace') { history.back(); e.preventDefault(); }
});
</script>
"""

LIST_BODY = """
<h1>__TITLE__</h1>
<p class="step">__STEP__</p>
<div class="rows" id="rows"></div>
<div class="msg" id="msg"></div>
<p class="hint">Enter turns one on or off. Left and right jump by letter.
Backspace goes back.</p>
<script>
__NAV__
let ITEMS = __ITEMS__;
const UP = __UP__;
const rows = document.getElementById('rows');
const msg = document.getElementById('msg');

ITEMS.forEach(it => {
  const el = document.createElement('div');
  el.className = 'row';
  el.innerHTML = '<div class="k"></div><div class="v"></div>';
  el.querySelector('.k').textContent = it.label;
  el.querySelector('.v').textContent =
    it.go ? '\\u203a' : (it.on ? '\\u2713 Following' : '');
  rows.appendChild(el);
});
const cells = [...rows.children];

// Left and right jump to the next initial. College football has seven hundred
// and sixty teams in it, and a list that long is not walkable one row at a time
// with a remote in your hand.
const letters = [];
ITEMS.forEach((it, i) => {
  const c = (it.label.match(/[A-Za-z0-9]/) || ['#'])[0].toUpperCase();
  if (!letters.length || letters[letters.length - 1].c !== c) {
    letters.push({ c: c, i: i });
  }
});
function jump(delta) {
  if (letters.length < 3) return;
  const here = nav ? nav.current() : 0;
  let at = 0;
  letters.forEach((l, n) => { if (l.i <= here) at = n; });
  const to = letters[Math.min(Math.max(at + delta, 0), letters.length - 1)];
  if (to) nav.to(to.i);
}

let nav = null;
function choose(i) {
  const it = ITEMS[i];
  if (it.go) { location.href = it.go; return; }
  fetch('/toggle', { method: 'POST', body: JSON.stringify(it) })
    .then(r => r.json())
    .then(r => {
      if (r.error) { msg.className = 'msg bad'; msg.textContent = r.error; return; }
      it.on = r.on;
      cells[i].querySelector('.v').textContent = it.on ? '\\u2713 Following' : '';
      msg.className = 'msg';
      msg.textContent = r.message || '';
    });
}
if (cells.length) {
  nav = tvnav(cells, choose, () => { location.href = UP; });
  addEventListener('keydown', e => {
    if (e.key === 'ArrowRight') jump(1);
    else if (e.key === 'ArrowLeft') jump(-1);
    else return;
    e.preventDefault();
  });
}
</script>
"""


def _card_html(game: dict) -> str:
    def side(team, other):
        lost = game["state"] == "post" and not team["winner"] and other["winner"]
        logo = (f'<img src="{html.escape(team["logo"], quote=True)}" alt="">'
                if team["logo"] else '<span style="width:42px"></span>')
        return (f'<div class="team{" lost" if lost else ""}">{logo}'
                f'<span class="rk">{html.escape(team["rank"])}</span>'
                f'<span class="ab">{html.escape(team["full"] or team["abbr"])}</span>'
                f'<span class="rec">{html.escape(team["record"])}</span>'
                f'<span class="sc">{html.escape(team["score"])}</span></div>')

    return (side(game["away"], game["home"]) + side(game["home"], game["away"])
            + f'<div class="foot">{html.escape(game["long_detail"] or game["detail"])}</div>'
            + (f'<div class="sit">{html.escape(game["situation"])}</div>'
               if game["situation"] else ""))


def run(sports) -> int:
    app = tvui.App("Scores")

    def entries():
        result = sports.today()
        games = list(result["games"])
        for game in games:
            game["go"] = f"/game?league={game['league']}&id={game['id']}"
        # First rather than last. On a busy Saturday there are forty cards
        # between the top of the page and the bottom of it, and settings that
        # far away are settings nobody finds. The highlight still starts on a
        # score, so what opens is a game.
        actions = [{"action": True, "label": "Choose leagues", "go": "/leagues"},
                   {"action": True, "label": "Follow teams",
                    "go": "/pick-league"}]
        message = "; ".join(f"{k}: {v}" for k, v in result["errors"].items())
        return actions + games, message

    def today(_query):
        games, message = entries()
        live = sum(1 for g in games if g.get("state") == "in")
        playing = sum(1 for g in games if not g.get("action"))
        step = f"{live} live now" if live else f"{playing} games"
        first = next((i for i, g in enumerate(games) if not g.get("action")),
                     0)
        return (TODAY_BODY
                .replace("__NAV__", tvui.NAV_JS)
                .replace("__STEP__", step)
                .replace("__START__", str(first))
                .replace("__GAMES__", json.dumps(games))
                + (f"<!-- {message} -->" if message else ""))

    def game(query):
        league = query.get("league", "")
        wanted = query.get("id", "")
        found = next((g for g in sports.espn.scoreboard(league)
                      if g["id"] == wanted), None)
        if found is None:
            return "<h1>That game is gone</h1><p class=\"step\">It may have " \
                   "dropped off the scoreboard.</p>"
        followed = sports.followed_team_ids()
        actions = [{"league": league, "id": side["id"],
                    "label": ("Stop following " if side["id"] in followed
                              else "Follow ") + (side["full"] or side["abbr"])}
                   for side in (found["away"], found["home"]) if side["id"]]
        detail = " · ".join(x for x in (
            found["venue"], found["network"], found["note"]) if x)
        if found["last_play"]:
            detail = (detail + "\n" if detail else "") + found["last_play"]
        return (GAME_BODY
                .replace("__NAV__", tvui.NAV_JS)
                .replace("__TITLE__", html.escape(
                    f'{found["away"]["abbr"]} at {found["home"]["abbr"]}'))
                .replace("__SUB__", html.escape(found["league_name"]))
                .replace("__CARD__", _card_html(found))
                .replace("__DETAIL__", html.escape(detail))
                .replace("__ACTS__", json.dumps(actions)))

    def leagues(_query):
        following = set(sports.settings()["leagues"])
        items = [{"kind": "league", "id": l["id"],
                  "label": f"{l['name']} · {l['sport']}",
                  "on": l["id"] in following} for l in sports.espn.LEAGUES]
        return (LIST_BODY
                .replace("__NAV__", tvui.NAV_JS)
                .replace("__TITLE__", "Leagues")
                .replace("__STEP__", "Which ones appear on the scores page")
                .replace("__UP__", json.dumps("/"))
                .replace("__ITEMS__", json.dumps(items)))

    def pick_league(_query):
        items = [{"kind": "open", "id": l["id"], "label": l["name"],
                  "on": False, "go": f"/teams?league={l['id']}"}
                 for l in sports.espn.LEAGUES]
        return (LIST_BODY
                .replace("__NAV__", tvui.NAV_JS)
                .replace("__TITLE__", "Follow teams")
                .replace("__STEP__", "Pick a league first")
                .replace("__UP__", json.dumps("/"))
                .replace("__ITEMS__", json.dumps(items)))

    def team_list(query):
        league = query.get("league", "")
        followed = sports.followed_team_ids()
        items = [{"kind": "team", "id": t["id"], "league": league,
                  "label": t["name"], "on": t["id"] in followed}
                 for t in sports.espn.teams(league)]
        name = sports.espn.BY_ID.get(league, {}).get("name", "Teams")
        return (LIST_BODY
                .replace("__NAV__", tvui.NAV_JS)
                .replace("__TITLE__", html.escape(name))
                .replace("__STEP__", "Followed teams come first on the "
                                     "scores page")
                .replace("__UP__", json.dumps("/pick-league"))
                .replace("__ITEMS__", json.dumps(items)))

    def do_data(_payload):
        try:
            games, message = entries()
        except Exception as exc:                              # noqa: BLE001
            return {"error": str(exc)[:160]}
        return {"games": games, "error": message}

    def do_toggle(payload):
        kind = payload.get("kind")
        if kind == "open":
            return {"on": False}
        if kind == "league":
            on = not payload.get("on")
            sports.follow_leagues([payload.get("id", "")], on)
            return {"on": on}
        if kind == "team":
            on = not payload.get("on")
            sports.follow_team(payload.get("league", ""),
                               payload.get("id", ""), on)
            return {"on": on}
        return {"error": "Nothing to change there."}

    def do_follow_team(payload):
        team_id = str(payload.get("id", ""))
        league = payload.get("league", "")
        on = team_id not in sports.followed_team_ids()
        sports.follow_team(league, team_id, on)
        label = payload.get("label", "")
        flipped = (label.replace("Stop following ", "Follow ") if not on
                   else label.replace("Follow ", "Stop following "))
        return {"label": flipped,
                "message": "Followed" if on else "No longer followed"}

    app.get("/", today)
    app.get("/game", game)
    app.get("/leagues", leagues)
    app.get("/pick-league", pick_league)
    app.get("/teams", team_list)
    app.post("/data", do_data)
    app.post("/toggle", do_toggle)
    app.post("/follow-team", do_follow_team)
    app.run()
    return 0
