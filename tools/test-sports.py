#!/usr/bin/env python3
"""Check the scores logic against a recorded scoreboard, offline.

The feed is undocumented, so the reading of it is the part that will break, and
the part worth pinning down. The fixture below is the shape ESPN actually sends,
trimmed: a game in progress with a clock and a down, a finished one with a
winner, one not started, and a competition that is not two-sided, which exists
and which nothing here can draw.

Run with: python3 tools/test-sports.py
"""
import importlib.machinery
import importlib.util
import json
import os
import sys
import tempfile
from pathlib import Path

sys.dont_write_bytecode = True

REPO = Path(__file__).resolve().parent.parent
SHARED = REPO / "image/overlay/usr/share/freetvos"
SOURCE = REPO / "image/overlay/usr/bin/freetvos-sports"

failures = []


def check(label, got, want):
    if got == want:
        print(f"  ok   {label}")
    else:
        print(f"  FAIL {label}\n         got  {got!r}\n         want {want!r}")
        failures.append(label)


def team(idx, abbr, name, score, rank=99, record="0-0", winner=False,
         home=True):
    return {
        "homeAway": "home" if home else "away",
        "score": score,
        "winner": winner,
        "curatedRank": {"current": rank},
        "records": [{"type": "total", "summary": record},
                    {"type": "homerecord", "summary": "9-9"}],
        "team": {"id": idx, "abbreviation": abbr, "displayName": name,
                 "shortDisplayName": name.split()[-1], "color": "ff8200",
                 "logo": f"https://a.espncdn.com/{idx}.png"},
    }


SCOREBOARD = {"events": [
    {"id": "1", "shortName": "TENN @ GT", "date": "2026-09-12T20:00Z",
     "status": {"type": {"state": "in", "shortDetail": "14:09 - 3rd",
                         "detail": "14:09 - 3rd Quarter"}},
     "competitions": [{
         "competitors": [team("59", "GT", "Georgia Tech", "10", 99, "0-1"),
                         team("2633", "TENN", "Tennessee", "24", 18, "1-0",
                              home=False)],
         "situation": {"shortDownDistanceText": "2nd & 5",
                       "downDistanceText": "2nd & 5 at TENN 41",
                       "possessionText": "TENN 41",
                       "lastPlay": {"text": "D.Bishop rush for 5 yards"}},
         "broadcasts": [{"market": "national", "names": ["ESPN"]}],
         "venue": {"fullName": "Bobby Dodd Stadium"},
     }]},
    {"id": "2", "shortName": "NE @ SEA", "date": "2026-09-12T17:00Z",
     "status": {"type": {"state": "post", "shortDetail": "Final"}},
     "competitions": [{
         "competitors": [team("26", "SEA", "Seattle", "20", 99, "1-0", True),
                         team("17", "NE", "New England", "13", 99, "0-1",
                              home=False)],
     }]},
    {"id": "3", "shortName": "TB @ CIN", "date": "2026-09-13T17:00Z",
     "status": {"type": {"state": "pre",
                         "shortDetail": "9/13 - 1:00 PM EDT"}},
     "competitions": [{
         "competitors": [team("4", "CIN", "Cincinnati", "0"),
                         team("27", "TB", "Tampa Bay", "0", home=False)],
     }]},
    # A competition with one side, which the feed does contain for some
    # events and which nothing here can draw.
    {"id": "4", "status": {"type": {"state": "pre"}},
     "competitions": [{"competitors": [team("9", "X", "Solo", "0")]}]},
]}

TEAMS = {"sports": [{"leagues": [{"teams": [
    {"team": {"id": "17", "abbreviation": "NE", "displayName": "New England",
              "logos": [{"href": "https://a.espncdn.com/17.png"}]}},
    {"team": {"id": "26", "abbreviation": "SEA", "displayName": "Seattle",
              "logos": [{"href": "https://a.espncdn.com/26.png"}]}},
]}]}]}


def load(root: Path):
    os.environ["FREETVOS_SPORTS_CONF"] = str(root / "sports.json")
    sys.path.insert(0, str(SHARED))
    sys.path.insert(0, str(SHARED / "sports"))
    loader = importlib.machinery.SourceFileLoader("freetvos_sports",
                                                  str(SOURCE))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


def main() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        sports = load(Path(tmp))
        espn = sports.espn

        asked = []

        def fake_get(url):
            asked.append(url)
            return TEAMS if "/teams" in url else SCOREBOARD

        espn._get = fake_get
        espn._cache.clear()

        print("reading a scoreboard")
        games = espn.scoreboard("ncaaf")
        check("the one-sided event is dropped", len(games), 3)
        live = games[0]
        check("who is home", live["home"]["abbr"], "GT")
        check("who is away", live["away"]["abbr"], "TENN")
        check("the score", (live["away"]["score"], live["home"]["score"]),
              ("24", "10"))
        check("the clock", live["detail"], "14:09 - 3rd")
        check("a ranking", live["away"]["rank"], "18")
        check("unranked is blank", live["home"]["rank"], "")
        check("the record", live["home"]["record"], "0-1")
        check("what is happening", live["situation"], "2nd & 5 at TENN 41")
        check("and not said twice", live["situation"].count("TENN 41"), 1)
        check("who is showing it", live["network"], "ESPN")
        check("the last play", live["last_play"], "D.Bishop rush for 5 yards")

        final = games[1]
        check("a winner is marked", final["home"]["winner"], True)
        check("and the loser is not", final["away"]["winner"], False)
        check("no situation once it is over", final["situation"], "")

        print("a break in play")
        paused = json.loads(json.dumps(SCOREBOARD))
        paused["events"][0]["status"]["type"]["shortDetail"] = "Halftime"
        espn._cache.clear()
        espn._get = lambda url: paused
        at_half = espn.scoreboard("ncaaf")[0]
        check("no down and distance at half time", at_half["situation"], "")
        check("but the clock still says so", at_half["detail"], "Halftime")
        espn._cache.clear()
        espn._get = fake_get

        upcoming = games[2]
        check("nothing has happened yet",
              (upcoming["away"]["score"], upcoming["home"]["score"]), ("", ""))
        check("only a time", upcoming["detail"], "9/13 - 1:00 PM EDT")

        print("what to look at first")
        order = sorted(games, key=lambda g: espn.sort_key(g, set()))
        check("live, then upcoming, then over",
              [g["state"] for g in order], ["in", "pre", "post"])
        order = sorted(games, key=lambda g: espn.sort_key(g, {"17"}))
        check("a followed team beats everything",
              [g["id"] for g in order], ["2", "1", "3"])

        print("leagues")
        check("the default is what somebody asked for",
              sports.settings()["leagues"], ["nfl", "ncaaf", "nba"])
        check("one can be added",
              "mlb" in sports.follow_leagues(["mlb"]), True)
        check("kept in the catalogue's order",
              sports.follow_leagues(["nhl"]),
              [l["id"] for l in espn.LEAGUES
               if l["id"] in {"nfl", "ncaaf", "nba", "mlb", "nhl"}])
        check("and removed", "mlb" in sports.follow_leagues(["mlb"], False),
              False)
        check("nonsense is refused",
              sports.follow_leagues(["notaleague"]) == sports.settings()["leagues"],
              True)

        print("teams")
        asked.clear()
        found = espn.teams("nfl")
        check("read and sorted", [t["abbr"] for t in found], ["NE", "SEA"])
        # Without this the answer is the first fifty of seven hundred, which
        # looks like a complete list and is not.
        check("every team is asked for",
              any("limit=1000" in url for url in asked), True)
        sports.follow_team("nfl", "26")
        check("followed", sports.followed_team_ids(), {"26"})
        check("with its name",
              sports.settings()["teams"][0]["name"], "Seattle")
        sports.follow_team("nfl", "26", False)
        check("and unfollowed", sports.followed_team_ids(), set())

        print("asking as little as possible")
        espn._cache.clear()
        asked.clear()
        espn.scoreboard("ncaaf")
        espn.scoreboard("ncaaf")
        check("a repeat inside the window is not a second request",
              len(asked), 1)

        print("when it goes wrong")
        def fail(_url):
            raise espn.EspnError("no network")
        espn._get = fail
        espn._cache.clear()
        result = espn.scoreboards(["nfl", "ncaaf"])
        check("every league reports its own failure",
              sorted(result["errors"]), ["ncaaf", "nfl"])
        check("and none of them take the page down",
              result["games"], {"nfl": [], "ncaaf": []})
        try:
            espn.scoreboard("madeup")
            check("an unknown league is refused", "no error", "an error")
        except espn.EspnError:
            check("an unknown league is refused", True, True)

    print()
    if failures:
        print(f"{len(failures)} check(s) failed")
        return 1
    print("all checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
