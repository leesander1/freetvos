"""Scores from ESPN's scoreboard feed.

The feed is public, needs no key and no account, and is not documented. That is
worth saying plainly: it is what every score widget on the internet is built on,
it has been stable for years, and it could still change shape without anybody
being told. Everything below is defensive for that reason. A field that moves
costs a blank line on a tile rather than a page that will not load.

Apple Sports has no public interface at all, so it is not an option however much
this looks like it.
"""
import json
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

BASE = "https://site.api.espn.com/apis/site/v2/sports"
TIMEOUT = 12
CACHE_SECONDS = 20

# The leagues a television in this house might care about. Ordered the way
# somebody would look for them rather than alphabetically.
LEAGUES = [
    {"id": "nfl", "path": "football/nfl", "name": "NFL", "sport": "Football"},
    {"id": "ncaaf", "path": "football/college-football",
     "name": "College Football", "sport": "Football"},
    {"id": "nba", "path": "basketball/nba", "name": "NBA",
     "sport": "Basketball"},
    {"id": "wnba", "path": "basketball/wnba", "name": "WNBA",
     "sport": "Basketball"},
    {"id": "ncaam", "path": "basketball/mens-college-basketball",
     "name": "Men's College Basketball", "sport": "Basketball"},
    {"id": "ncaaw", "path": "basketball/womens-college-basketball",
     "name": "Women's College Basketball", "sport": "Basketball"},
    {"id": "mlb", "path": "baseball/mlb", "name": "MLB", "sport": "Baseball"},
    {"id": "nhl", "path": "hockey/nhl", "name": "NHL", "sport": "Hockey"},
    {"id": "mls", "path": "soccer/usa.1", "name": "MLS", "sport": "Soccer"},
    {"id": "epl", "path": "soccer/eng.1", "name": "Premier League",
     "sport": "Soccer"},
    {"id": "ucl", "path": "soccer/uefa.champions",
     "name": "Champions League", "sport": "Soccer"},
]

BY_ID = {league["id"]: league for league in LEAGUES}

_cache: dict = {}
_lock = threading.Lock()


class EspnError(Exception):
    pass


def _get(url: str):
    # No User-Agent of our own, which is the opposite of what you would expect
    # and is what the feed requires. ESPN's edge answers a plain scripting
    # agent, which is what urllib sends when nothing is set, and refuses with a
    # 403 both a made-up product name and a full browser string. That was found
    # the hard way: the same code that worked from a laptop stopped working the
    # moment it identified itself. Adding one back will break this.
    request = urllib.request.Request(url, headers={
        "Accept": "application/json",
    })
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
            return json.loads(response.read())
    except (urllib.error.URLError, OSError) as exc:
        raise EspnError(f"could not reach ESPN: {exc}") from exc
    except ValueError as exc:
        raise EspnError("ESPN sent something unreadable") from exc


def _cached(url: str):
    """One answer per league per twenty seconds.

    The page refreshes itself while somebody is watching a close game, and
    every one of those refreshes would otherwise be a fresh request per league.
    """
    now = time.time()
    with _lock:
        hit = _cache.get(url)
        if hit and now - hit[0] < CACHE_SECONDS:
            return hit[1]
    data = _get(url)
    with _lock:
        _cache[url] = (now, data)
    return data


# ---------------------------------------------------------------------------
# Reading one game.
# ---------------------------------------------------------------------------


def _record(competitor: dict) -> str:
    for record in competitor.get("records") or []:
        if record.get("type") in ("total", "overall"):
            return record.get("summary") or ""
    records = competitor.get("records") or []
    return (records[0].get("summary") or "") if records else ""


def _rank(competitor: dict) -> str:
    rank = ((competitor.get("curatedRank") or {}).get("current"))
    # 99 is ESPN's way of saying unranked, and anything past 25 is not a
    # ranking anyone quotes.
    return str(rank) if isinstance(rank, int) and 1 <= rank <= 25 else ""


def _side(competitor: dict, state: str = "") -> dict:
    team = competitor.get("team") or {}
    return {
        "abbr": team.get("abbreviation") or team.get("shortDisplayName") or "",
        "name": team.get("shortDisplayName") or team.get("displayName") or "",
        "full": team.get("displayName") or "",
        "id": str(team.get("id") or ""),
        "logo": team.get("logo") or "",
        "colour": f"#{team.get('color')}" if team.get("color") else "",
        # Nothing has happened yet before kick-off, and a pair of zeroes on a
        # tile reads as a scoreless game in progress.
        "score": ("" if state == "pre" else (competitor.get("score") or "")),
        "record": _record(competitor),
        "rank": _rank(competitor),
        "winner": bool(competitor.get("winner")),
    }


# Nothing is happening during a break, but the feed keeps sending the last
# thing that did, so a card at half time would otherwise show a down and
# distance that stopped being true ten minutes ago.
BREAKS = ("halftime", "end of", "delayed", "postponed")


def _situation(competition: dict, detail: str = "") -> str:
    """The one line that says what is happening right now, where there is one."""
    if any(word in detail.lower() for word in BREAKS):
        return ""
    situation = competition.get("situation") or {}
    # The short form and the place, not the long form and the place: the long
    # one already ends in the place, so combining them says it twice.
    down = situation.get("shortDownDistanceText") or ""
    where = situation.get("possessionText") or ""
    if down and where:
        return f"{down} at {where}"
    if down or situation.get("downDistanceText"):
        return down or situation["downDistanceText"]
    balls, strikes = situation.get("balls"), situation.get("strikes")
    if balls is not None and strikes is not None:
        outs = situation.get("outs")
        line = f"{balls}-{strikes}"
        if outs is not None:
            line += f", {outs} out" + ("" if outs == 1 else "s")
        return line
    return ""


def _network(competition: dict) -> str:
    for broadcast in competition.get("broadcasts") or []:
        names = broadcast.get("names") or []
        if names:
            return names[0]
    return ""


def normalise(event: dict, league: dict) -> dict:
    competition = (event.get("competitions") or [{}])[0]
    status = event.get("status") or competition.get("status") or {}
    kind = status.get("type") or {}
    competitors = competition.get("competitors") or []

    state = kind.get("state") or "pre"
    home = next((c for c in competitors if c.get("homeAway") == "home"), None)
    away = next((c for c in competitors if c.get("homeAway") == "away"), None)
    if home is None or away is None:
        # Some competitions are not two-sided. Nothing here can draw those.
        return {}

    return {
        "id": str(event.get("id") or ""),
        "league": league["id"],
        "league_name": league["name"],
        "state": state,
        "detail": kind.get("shortDetail") or kind.get("description") or "",
        "long_detail": kind.get("detail") or "",
        "start": event.get("date") or "",
        "home": _side(home, state),
        "away": _side(away, state),
        "network": _network(competition),
        "situation": (_situation(competition,
                                 kind.get("shortDetail") or "")
                      if state == "in" else ""),
        "last_play": ((competition.get("situation") or {}).get("lastPlay")
                      or {}).get("text", "") if state == "in" else "",
        "venue": ((competition.get("venue") or {}).get("fullName") or ""),
        "note": (competition.get("notes") or [{}])[0].get("headline", ""),
    }


# ---------------------------------------------------------------------------
# Reading a league.
# ---------------------------------------------------------------------------


def scoreboard(league_id: str, date: str = "") -> list:
    league = BY_ID.get(league_id)
    if not league:
        raise EspnError(f"unknown league: {league_id}")
    url = f"{BASE}/{league['path']}/scoreboard"
    if date:
        url += "?" + urllib.parse.urlencode({"dates": date})
    data = _cached(url)
    games = []
    for event in data.get("events") or []:
        game = normalise(event, league)
        if game:
            games.append(game)
    return games


def scoreboards(league_ids: list, date: str = "") -> dict:
    """Several leagues at once, because one at a time is a visible wait.

    Failures are per league. One league being unreachable should cost that
    league's row, not the whole page.
    """
    results: dict = {}
    errors: dict = {}

    def work(league_id):
        try:
            results[league_id] = scoreboard(league_id, date)
        except EspnError as exc:
            errors[league_id] = str(exc)
            results[league_id] = []

    threads = [threading.Thread(target=work, args=(lid,), daemon=True)
               for lid in league_ids]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=TIMEOUT + 3)
    return {"games": results, "errors": errors}


def teams(league_id: str) -> list:
    """Every team in a league, for choosing the ones to follow."""
    league = BY_ID.get(league_id)
    if not league:
        return []
    # The limit is not optional. Without it the answer is the first fifty
    # teams of seven hundred and sixty, which looks like a complete list and is
    # not: most of college football is simply missing from it.
    data = _cached(f"{BASE}/{league['path']}/teams?limit=1000")
    out = []
    for group in (data.get("sports") or [{}])[0].get("leagues") or []:
        for entry in group.get("teams") or []:
            team = entry.get("team") or {}
            if not team.get("id"):
                continue
            out.append({
                "id": str(team["id"]),
                "league": league_id,
                "abbr": team.get("abbreviation") or "",
                "name": team.get("displayName") or team.get("name") or "",
                "logo": (team.get("logos") or [{}])[0].get("href", ""),
            })
    out.sort(key=lambda t: t["name"].lower())
    return out


def sort_key(game: dict, followed: set):
    """Games worth looking at first: yours, then live, then about to start.

    A finished game is the least urgent thing on the page and a live one the
    most, which is the opposite of the order a date sort would give.
    """
    state_order = {"in": 0, "pre": 1, "post": 2}
    mine = not (game["home"]["id"] in followed or game["away"]["id"] in followed)
    return (mine, state_order.get(game["state"], 3), game.get("start", ""))
