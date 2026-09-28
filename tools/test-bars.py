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

    print("what a custom bar can read")
    ticker = sources.parse_ticker
    own = json.dumps({"items": [
        {"label": "Sales today", "value": "$12,400", "change": "4%", "direction": "up"},
        {"label": "Returns", "value": "18", "direction": "sideways"},
        {"label": "", "value": "no label, dropped"},
        {"label": "Top store", "star": True}]}).encode()
    items = ticker(own)
    check("FreeTVOS JSON, drawn like prices",
          items[0], {"label": "Sales today", "direction": "up",
                     "value": "$12,400", "change": "4%"})
    check("an unknown direction is flat", items[1]["direction"], "flat")
    check("an item with no label is left out", len(items), 3)
    check("a star is kept", items[2].get("star"), True)
    check("a bare list works too",
          [i["label"] for i in ticker(b'[{"label": "A"}, {"label": "B"}]')], ["A", "B"])
    check("a JSON Feed is headlines",
          [i["label"] for i in ticker(jsonfeed.encode())], ["One", "Two"])
    check("so is RSS", [i["label"] for i in ticker(rss)], ["First & foremost", "Second"])
    check("plain text is a line an item, blank lines skipped",
          [i["label"] for i in ticker(b"Welcome to ACME\n\n  Canteen opens at noon  \n")],
          ["Welcome to ACME", "Canteen opens at noon"])
    check("entities in text are read",
          [i["label"] for i in ticker(b"Plain &amp; simple")], ["Plain & simple"])
    try:
        ticker(b"<html><body>not a feed")
        check("a web page is still refused", "accepted", "refused")
    except sources.SourceError:
        check("a web page is still refused", "refused", "refused")
    long_label = ticker(json.dumps({"items": [{"label": "x" * 500}]}).encode())
    check("a long label is cut, not refused", len(long_label[0]["label"]), 120)
    with tempfile.TemporaryDirectory() as tmp:
        note = Path(tmp) / "board.txt"
        note.write_text("Fire drill at 3\n")
        check("a file on the television, by path",
              [i["label"] for i in sources.ticker(str(note))], ["Fire drill at 3"])
        check("or as file://",
              [i["label"] for i in sources.ticker(note.as_uri())], ["Fire drill at 3"])
        try:
            sources.ticker(str(Path(tmp) / "missing.txt"))
            check("a missing file says so", "read", "error")
        except sources.SourceError as exc:
            check("a missing file says so", "could not read" in str(exc), True)

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

        print("more than one bar of your own")
        # A file written before bars had kinds: ids only.
        Path(os.environ["FREETVOS_BARS_CONF"]).write_text(json.dumps({"bars": [
            {"id": "custom", "enabled": True, "title": "OLD"},
            {"id": "stocks"}, {"id": "nonsense"}]}))
        data = bars.settings()
        check("an older settings file still reads",
              [(b["id"], b["kind"]) for b in data["bars"]],
              [("custom", "custom"), ("stocks", "stocks"), ("sports", "sports")])
        check("with its values kept", data["bars"][0]["title"], "OLD")
        check("and the display at its defaults",
              (data["size"], data["layout"], data["rotate_every"]),
              ("full", "stacked", 20))

        second = bars.add_custom()
        third = bars.add_custom()
        check("new bars get their own ids", (second, third), ("custom-2", "custom-3"))
        bars.update_bar("custom", enabled=True, when="always", message="",
                        feed="https://one.example/feed")
        bars.update_bar(second, enabled=True, when="always", title="TWO",
                        feed="https://two.example/feed", accent="#FF0000")
        bars.update_bar(third, accent="red")
        asked = []
        feeder = bars.Feeder({"custom": lambda bar: (asked.append(bar["id"]) or
                                                     [f"from {bar['id']}"]),
                              "market": lambda bar: "closed",
                              "stocks": lambda bar: [], "sports": lambda bar: []})
        result = bars.build(bars.settings(), feeder, now)
        by_id = {b["id"]: b for b in result["bars"]}
        check("each custom bar reads its own feed",
              (by_id["custom"]["items"][0]["label"], by_id[second]["items"][0]["label"]),
              ("from custom", "from custom-2"))
        check("and is asked separately", sorted(asked), ["custom", "custom-2"])
        check("a colour is passed on", by_id[second]["accent"], "#FF0000")
        check("one that is not a colour is not",
              "accent" in bars.build(bars.settings(), feeder, now)["bars"][0], False)
        check("the service says how to draw them",
              (result["size"], result["layout"], result["rotate_every"]),
              ("full", "stacked", 20))

        bars.remove_bar(third)
        check("an extra custom bar can be removed",
              [b["id"] for b in bars.settings()["bars"]].count(third), 0)
        for refused, label in (("stocks", "the stocks bar is switched off, not removed"),
                               ("nonsense", "a bar that does not exist")):
            try:
                bars.remove_bar(refused)
                check(label, "removed", "refused")
            except ValueError:
                check(label, "refused", "refused")
        bars.remove_bar(second)
        try:
            bars.remove_bar("custom")
            check("the last custom bar stays", "removed", "refused")
        except ValueError:
            check("the last custom bar stays", "refused", "refused")

        print("how the bars look")
        bars.update_display(size="thin", layout="rotate", rotate_every=2)
        data = bars.settings()
        check("thin, taking turns", (data["size"], data["layout"]), ("thin", "rotate"))
        check("a turn is never shorter than five seconds", data["rotate_every"], 5)
        for bad in ({"size": "huge"}, {"layout": "diagonal"}):
            try:
                bars.update_display(**bad)
                check(f"refused: {bad}", "accepted", "refused")
            except ValueError:
                check(f"refused: {bad}", "refused", "refused")

        print("the settings page")
        sys.path.insert(0, str(REPO / "image/overlay/usr/share/freetvos"))
        import barsui
        rows = barsui.rows_for(bars)
        check("it opens with how the bars look",
              [r.get("key") for r in rows[1:4]], ["size", "layout", "rotate_every"])
        check("and ends with a way to add a bar",
              rows[-1].get("action"), "add_custom")
        barsui.apply(bars, {"bar": barsui.DISPLAY, "action": "add_custom"})
        added = [b for b in bars.settings()["bars"] if b["kind"] == "custom"][-1]
        check("adding from the page", added["id"], "custom-2")
        check("an extra bar can be removed from the page",
              any(r.get("action") == "remove" and r["bar"] == added["id"]
                  for r in barsui.rows_for(bars)), True)
        try:
            barsui.apply(bars, {"bar": added["id"], "key": "accent", "value": "blue"})
            check("a colour that is not one is refused", "saved", "refused")
        except ValueError:
            check("a colour that is not one is refused", "refused", "refused")
        barsui.apply(bars, {"bar": added["id"], "key": "accent", "value": "#123abc"})
        check("and one that is, kept",
              bars.find(bars.settings(), added["id"])["accent"], "#123abc")
        barsui.apply(bars, {"bar": barsui.DISPLAY, "key": "layout", "value": "stacked"})
        check("the layout from the page", bars.settings()["layout"], "stacked")
        check("with nothing to rotate, no turn length is asked",
              any(r.get("key") == "rotate_every" for r in barsui.rows_for(bars)), False)

    print()
    if failures:
        print(f"{len(failures)} check(s) failed")
        return 1
    print("all checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
