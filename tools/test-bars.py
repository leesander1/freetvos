#!/usr/bin/env python3
"""Check what the bars show and when, against recorded replies, offline.

The rules are the part worth pinning down: whether the market is open, whether
a window that runs past midnight includes one in the morning, whether a bar
with nothing to say stays off rather than drawing an empty strip across a film.
The fixtures are real replies from Nasdaq and a real Atom feed, saved once.

Run with: python3 tools/test-bars.py
"""
import datetime as dt
import importlib.machinery
import importlib.util
import json
import os
import sys
import tempfile
from pathlib import Path

sys.dont_write_bytecode = True

REPO = Path(__file__).resolve().parent.parent
FIXTURES = REPO / "tools/fixtures"
sys.path.insert(0, str(REPO / "image/overlay/usr/share/freetvos/bars"))

import sources                                              # noqa: E402

failures = []


def check(label, got, want):
    if got == want:
        print(f"  ok   {label}")
    else:
        print(f"  FAIL {label}\n         got  {got!r}\n         want {want!r}")
        failures.append(label)


EASTERN = sources.EASTERN


def at(text: str) -> dt.datetime:
    """A moment in New York, where the market keeps its hours."""
    return dt.datetime.fromisoformat(text).replace(tzinfo=EASTERN)


def main() -> int:
    print("stock prices")
    quotes = sources.parse_quotes(
        json.loads((FIXTURES / "nasdaq-watchlist.json").read_text()))
    check("every symbol read", [q["label"] for q in quotes],
          ["AAPL", "NVDA", "SPY", "COMP"])
    check("the dollar sign is dropped", "$" in quotes[0]["value"], False)
    check("a direction for each", all(q["direction"] in ("up", "down", "flat")
                                      for q in quotes), True)
    check("the sign is carried by the arrow, not the number",
          any(q["change"].startswith(("+", "-")) for q in quotes), False)
    check("an index is asked for as an index", sources.asset_class("comp"),
          "index")
    check("a fund as a fund", sources.asset_class("SPY"), "etf")
    check("anything else as a company", sources.asset_class("AAPL"), "stocks")
    check("an empty reply is no quotes", sources.parse_quotes({}), [])

    print("finding a stock")
    tesla = sources.parse_search(json.loads(
        (FIXTURES / "nasdaq-search-tesla.json").read_text()))
    check("the company comes first", tesla[0]["symbol"], "TSLA")
    check("structured notes and mutual funds are not offered",
          [r["symbol"] for r in tesla if not r["symbol"].isalpha()
           and "." not in r["symbol"]], [])
    check("the share class is taken off the name", tesla[0]["name"], "Tesla, Inc.")
    check("each result knows its kind",
          {r["asset"] for r in tesla} <= {"stocks", "etf", "index"}, True)
    apple = sources.parse_search(json.loads(
        (FIXTURES / "nasdaq-search-apple.json").read_text()), limit=2)
    check("a limit", len(apple), 2)
    check("an empty reply finds nothing", sources.parse_search({}), [])
    check("an empty search asks nothing", sources.search_symbols("  "), [])

    print("asking for prices by kind")
    asked = []
    real_get = sources._get
    sources._get = lambda url, headers=None: (asked.append(url) or
                                              b'{"data": []}')
    sources.quotes(["gld", "AAPL"], {"GLD": "etf"})
    sources._get = real_get
    check("a kind from search is used", "symbol=gld%7cetf" in asked[0], True)
    check("an unknown symbol falls back to the guess",
          "symbol=aapl%7cstocks" in asked[0], True)

    print("whether the market is open")
    check("read from Nasdaq",
          sources.parse_market(json.loads(
              (FIXTURES / "nasdaq-market-info.json").read_text())) in
          ("open", "closed"), True)
    check("pre-market is not open",
          sources.parse_market({"data": {"mrktStatus": "Pre-Market"}}),
          "closed")
    check("after hours is not open",
          sources.parse_market({"data": {"mrktStatus": "After-Hours"}}),
          "closed")
    check("open is open", sources.parse_market({"data": {"mrktStatus": "Open"}}),
          "open")
    check("nothing said is unknown", sources.parse_market({}), "unknown")
    clock = sources.market_hours_by_clock
    check("a Tuesday at ten is open", clock(at("2026-09-15T10:00")), "open")
    check("half past nine exactly is open", clock(at("2026-09-15T09:30")), "open")
    check("four o'clock exactly is closed", clock(at("2026-09-15T16:00")),
          "closed")
    check("Saturday is closed", clock(at("2026-09-19T12:00")), "closed")
    check("the clock is New York's, not the television's",
          clock(dt.datetime(2026, 9, 15, 15, 0, tzinfo=dt.timezone.utc)), "open")

    print("scores")
    games = [
        {"action": True, "label": "Choose leagues"},
        {"state": "in", "detail": "9:21 - 2nd", "followed": True,
         "away": {"abbr": "DEN", "score": "7"}, "home": {"abbr": "KC", "score": "7"}},
        {"state": "pre", "detail": "9/18 - 7:30 PM EDT",
         "away": {"abbr": "MIA", "score": ""}, "home": {"abbr": "WAKE", "score": ""}},
        {"state": "post", "detail": "Final",
         "away": {"abbr": "NE", "score": "10"}, "home": {"abbr": "SEA", "score": "13"}},
    ]
    items = sources.score_items(games)
    check("settings cards are not games", len(items), 3)
    check("a live score", (items[0]["label"], items[0]["value"],
                           items[0]["direction"]),
          ("DEN @ KC", "7-7", "live"))
    check("a followed team is starred", items[0]["star"], True)
    check("no score before kick-off", items[1]["value"], "")
    check("only live games when asked",
          [i["label"] for i in sources.score_items(games, only_live=True)],
          ["DEN @ KC"])
    check("something is live", sources.any_live(games), True)
    check("but not for a team nobody follows",
          sources.any_live([g for g in games if not g.get("followed")],
                           followed_only=True), False)

    print("feeds")
    atom = sources.parse_feed((FIXTURES / "feed.atom").read_bytes())
    check("an Atom feed", len(atom) > 0, True)
    rss = (b'<?xml version="1.0"?><rss><channel><title>News</title>'
           b'<item><title>First &amp; foremost</title></item>'
           b'<item><title><![CDATA[<b>Second</b>]]></title></item>'
           b'</channel></rss>')
    check("an RSS feed, entities and markup taken out",
          sources.parse_feed(rss), ["First & foremost", "Second"])
    check("the channel's own title is not a headline",
          "News" in sources.parse_feed(rss), False)
    jsonfeed = json.dumps({"version": "https://jsonfeed.org/version/1.1",
                           "items": [{"title": "One"}, {"content_text": "Two"}]})
    check("a JSON Feed", sources.parse_feed(jsonfeed.encode()), ["One", "Two"])
    check("a limit", len(sources.parse_feed(rss, limit=1)), 1)
    try:
        sources.parse_feed(b"<html><body>not a feed")
        check("a web page is refused", "accepted", "refused")
    except sources.SourceError:
        check("a web page is refused", "refused", "refused")

    print("time windows")
    win = sources.in_window
    check("inside", win("07:00-09:30", at("2026-09-15T08:15")), True)
    check("at the end is outside", win("07:00-09:30", at("2026-09-15T09:30")),
          False)
    check("past midnight, late", win("22:00-02:00", at("2026-09-15T23:30")), True)
    check("past midnight, early", win("22:00-02:00", at("2026-09-16T01:00")), True)
    check("past midnight, midday", win("22:00-02:00", at("2026-09-15T12:00")),
          False)
    check("nonsense is never", win("whenever", at("2026-09-15T12:00")), False)
    check("no days means every day", sources.on_day([], at("2026-09-19T12:00")),
          True)
    check("weekdays only, on a Saturday",
          sources.on_day(["mon", "tue", "wed", "thu", "fri"],
                         at("2026-09-19T12:00")), False)

    print("whether a bar shows")
    show = sources.should_show
    now = at("2026-09-15T10:00")
    check("off is off", show({"enabled": False, "when": "always"}, now, {}), False)
    check("always is always", show({"enabled": True, "when": "always"}, now, {}),
          True)
    check("market open", show({"enabled": True, "when": "market"}, now,
                              {"market": "open"}), True)
    check("market closed", show({"enabled": True, "when": "market"}, now,
                                {"market": "closed"}), False)
    check("market unknown stays off", show({"enabled": True, "when": "market"},
                                           now, {"market": "unknown"}), False)
    check("games live", show({"enabled": True, "when": "live"}, now,
                             {"live": True}), True)
    check("no games", show({"enabled": True, "when": "live"}, now,
                           {"live": False}), False)
    check("a window", show({"enabled": True, "when": "window",
                            "window": "09:00-11:00"}, now, {}), True)
    check("a day it is not allowed on",
          show({"enabled": True, "when": "always", "days": ["sat", "sun"]},
               now, {}), False)

    print("the service's decisions")
    with tempfile.TemporaryDirectory() as tmp:
        os.environ["FREETVOS_BARS_CONF"] = str(Path(tmp) / "bars.json")
        loader = importlib.machinery.SourceFileLoader(
            "freetvos_bars", str(REPO / "image/overlay/usr/bin/freetvos-bars"))
        spec = importlib.util.spec_from_loader(loader.name, loader)
        bars = importlib.util.module_from_spec(spec)
        loader.exec_module(bars)

        data = bars.settings()
        check("three bars, all off to begin with",
              [(b["id"], b["enabled"]) for b in data["bars"]],
              [("stocks", False), ("sports", False), ("custom", False)])
        bars.update_bar("stocks", enabled=True, when="always")
        bars.update_bar("custom", enabled=True, when="always",
                        title="ACME", message="Welcome",
                        feed="https://news.example/feed.xml")
        check("changes are kept", bars.settings()["bars"][0]["enabled"], True)
        bars.move_bar("custom", -2)
        check("the stack can be reordered",
              [b["id"] for b in bars.settings()["bars"]],
              ["custom", "stocks", "sports"])
        bars.move_bar("custom", -5)
        check("and not past the top",
              bars.settings()["bars"][0]["id"], "custom")

        answers = {"stocks": quotes, "sports": games, "custom": ["Headline"],
                   "market": "closed"}
        feeder = bars.Feeder({name: (lambda bar, n=name: answers[n])
                              for name in answers})
        result = bars.build(bars.settings(), feeder, now)
        check("stacked in the order chosen", [b["id"] for b in result["bars"]],
              ["custom", "stocks"])
        check("the custom bar carries the message then the headlines",
              [i["label"] for i in result["bars"][0]["items"]],
              ["Welcome", "Headline"])
        check("with its title", result["bars"][0]["title"], "ACME")
        check("a bar left off says why", result["notes"]["sports"], "off")

        bars.update_bar("stocks", when="market")
        result = bars.build(bars.settings(), feeder, now)
        check("stocks leave when the market closes",
              [b["id"] for b in result["bars"]], ["custom"])
        check("and say so", result["notes"]["stocks"], "market closed")

        bars.update_bar("custom", feed="")
        result = bars.build(bars.settings(), feeder, now)
        check("clearing the feed takes its headlines off at once",
              [i["label"] for i in result["bars"][0]["items"]], ["Welcome"])

        bars.update_bar("custom", message="", feed="")
        answers["custom"] = []
        result = bars.build(bars.settings(), feeder, now)
        check("a bar with nothing to say does not draw an empty strip",
              [b["id"] for b in result["bars"]], [])

        print("choosing stocks")
        bars.set_stocks(["tsla", "TSLA", " gld ", "AAPL"],
                        {"TSLA": "stocks", "GLD": "etf", "OLD": "stocks"})
        stock_bar = next(b for b in bars.settings()["bars"] if b["id"] == "stocks")
        check("in order, upper case, each once",
              stock_bar["symbols"], ["TSLA", "GLD", "AAPL"])
        check("kinds kept only for chosen symbols",
              stock_bar["assets"], {"TSLA": "stocks", "GLD": "etf"})

        calls = {"n": 0}

        def flaky(bar):
            calls["n"] += 1
            if calls["n"] > 1:
                raise sources.SourceError("gone")
            return quotes

        feeder = bars.Feeder({"stocks": flaky})
        feeder.get("stocks", {}, "a")
        feeder.cache["stocks"] = (0, "a", quotes)          # make it stale
        kept = feeder.get("stocks", {}, "a")
        check("a failed refresh keeps the last good prices", kept, quotes)
        check("and remembers why", feeder.errors.get("stocks"), "gone")

    print()
    if failures:
        print(f"{len(failures)} check(s) failed")
        return 1
    print("all checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
