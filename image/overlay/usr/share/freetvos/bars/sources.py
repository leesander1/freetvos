"""What goes on the bars, and when each bar is allowed to show.

Three kinds of bar, stacked at the bottom of the screen above whatever is
playing: stock prices, live scores, and one you feed yourself with a message, a
logo and a news feed. Each one has its own schedule, because a stock ticker at
midnight on a Sunday is noise and so is a scores bar with nothing on.

Everything here is data and rules. The drawing is the QML overlay's job and the
timing is the service's; this module neither draws nor sleeps, which is what
lets it be tested against recorded replies on any machine.
"""
import datetime as dt
import html
import json
import re
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from zoneinfo import ZoneInfo

TIMEOUT = 12
EASTERN = ZoneInfo("America/New_York")

# Nasdaq's own site API. No key and no account, and undocumented in the same
# way ESPN's scoreboard is: stable for years, promised to nobody. Unlike ESPN it
# refuses a request that does not look like a browser, so it gets one.
NASDAQ = "https://api.nasdaq.com/api"
BROWSER = ("Mozilla/5.0 (X11; Linux aarch64) AppleWebKit/537.36 "
           "(KHTML, like Gecko) Chrome/120.0 Safari/537.36")


class SourceError(Exception):
    pass


def _get(url: str, headers: dict | None = None) -> bytes:
    request = urllib.request.Request(url, headers=headers or {})
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
            return response.read()
    except (urllib.error.URLError, OSError) as exc:
        raise SourceError(f"could not reach {url.split('/')[2]}: {exc}") from exc


# ---------------------------------------------------------------------------
# Stocks.
# ---------------------------------------------------------------------------

# How Nasdaq wants each symbol described. Indexes and funds are looked up in a
# different table from companies, and asking for one in the wrong table returns
# nothing rather than an error.
INDEXES = {"COMP", "NDX", "SPX", "DJI", "RUT", "VIX"}
FUNDS = {"SPY", "QQQ", "DIA", "IWM", "VOO", "VTI", "VT", "GLD", "TLT", "ARKK"}


def asset_class(symbol: str) -> str:
    symbol = symbol.upper()
    if symbol in INDEXES:
        return "index"
    if symbol in FUNDS:
        return "etf"
    return "stocks"


def parse_quotes(payload: dict) -> list:
    """Nasdaq's watchlist reply, as ticker items."""
    out = []
    for row in (payload or {}).get("data") or []:
        symbol = (row.get("symbol") or "").upper()
        price = (row.get("lastSalePrice") or "").replace("$", "").strip()
        if not symbol or not price:
            continue
        change = (row.get("percentageChange") or "").strip()
        direction = (row.get("deltaIndicator") or "").lower()
        if direction not in ("up", "down"):
            direction = ("down" if change.startswith("-")
                         else "up" if change.startswith("+") else "flat")
        out.append({"label": symbol, "value": price,
                    "change": change.lstrip("+-"), "direction": direction})
    return out


def quotes(symbols: list, assets: dict | None = None) -> list:
    """Prices for the chosen symbols, in the order chosen.

    assets carries each symbol's kind as the search reported it. A symbol
    picked from search is asked for in the right table; one typed by hand falls
    back to the guess.
    """
    wanted = [s.strip().upper() for s in symbols if s.strip()]
    if not wanted:
        return []
    known = {k.upper(): v for k, v in (assets or {}).items()}
    query = "&".join(f"symbol={s.lower()}%7c{known.get(s) or asset_class(s)}"
                     for s in wanted)
    raw = _get(f"{NASDAQ}/quote/watchlist?{query}",
               {"User-Agent": BROWSER, "Accept": "application/json"})
    try:
        return parse_quotes(json.loads(raw))
    except ValueError as exc:
        raise SourceError("Nasdaq sent something unreadable") from exc


# What search results are worth offering. Nasdaq's lookup also returns
# structured notes and mutual funds with names three lines long, which is what
# searching "tesla" mostly finds.
SEARCHABLE = {"STOCKS": "stocks", "ETF": "etf", "INDEX": "index"}


def parse_search(payload: dict, limit: int = 8) -> list:
    """Nasdaq's lookup reply, as symbols someone would actually want."""
    out, seen = [], set()
    for row in (payload or {}).get("data") or []:
        symbol = (row.get("symbol") or "").strip().upper()
        kind = SEARCHABLE.get((row.get("asset") or "").upper())
        if not symbol or not kind or symbol in seen:
            continue
        seen.add(symbol)
        name = (row.get("name") or "").strip()
        # Nasdaq's names end in the share class, which is noise on a TV.
        name = re.sub(r"\s+(Common Stock|Common Shares|Class [A-C] Common Stock|"
                      r"Ordinary Shares|American Depositary Shares)\b.*$", "",
                      name, flags=re.I)
        out.append({"symbol": symbol, "name": name, "asset": kind,
                    "exchange": row.get("exchange") or ""})
        if len(out) >= limit:
            break
    return out


def search_symbols(query: str, limit: int = 8) -> list:
    query = (query or "").strip()
    if not query:
        return []
    raw = _get(f"{NASDAQ}/autocomplete/slookup/10?"
               f"search={urllib.parse.quote(query)}",
               {"User-Agent": BROWSER, "Accept": "application/json"})
    try:
        return parse_search(json.loads(raw), limit)
    except ValueError as exc:
        raise SourceError("Nasdaq sent something unreadable") from exc


def parse_market(payload: dict) -> str:
    """open, closed, or unknown, from Nasdaq's market-info reply."""
    data = (payload or {}).get("data") or {}
    status = (data.get("mrktStatus") or data.get("marketIndicator") or "").lower()
    if "open" in status and "pre" not in status and "after" not in status:
        return "open"
    if status:
        return "closed"
    return "unknown"


def market_hours_by_clock(now: dt.datetime) -> str:
    """The regular session by the clock alone, when Nasdaq cannot be asked.

    Right on an ordinary weekday and wrong on the nine or ten exchange holidays
    a year, which is why it is only the fallback.
    """
    local = now.astimezone(EASTERN)
    if local.weekday() >= 5:
        return "closed"
    minutes = local.hour * 60 + local.minute
    return "open" if 9 * 60 + 30 <= minutes < 16 * 60 else "closed"


def market_status(now: dt.datetime) -> str:
    try:
        raw = _get(f"{NASDAQ}/market-info",
                   {"User-Agent": BROWSER, "Accept": "application/json"})
        found = parse_market(json.loads(raw))
        if found != "unknown":
            return found
    except (SourceError, ValueError):
        pass
    return market_hours_by_clock(now)


# ---------------------------------------------------------------------------
# Sports.
# ---------------------------------------------------------------------------


def score_items(games: list, only_live: bool = False) -> list:
    """Scores as ticker items, live games first and followed teams marked."""
    out = []
    for game in games:
        if game.get("action"):
            continue
        state = game.get("state")
        if only_live and state != "in":
            continue
        away, home = game.get("away") or {}, game.get("home") or {}
        if state == "pre":
            value = ""
        else:
            value = f"{away.get('score', '')}-{home.get('score', '')}"
        out.append({
            "label": f"{away.get('abbr', '')} @ {home.get('abbr', '')}",
            "value": value,
            "change": game.get("detail", ""),
            "direction": "live" if state == "in" else "flat",
            "star": bool(game.get("followed")),
        })
    return out


def any_live(games: list, followed_only: bool = False) -> bool:
    return any(g.get("state") == "in" and (g.get("followed") or not followed_only)
               for g in games if not g.get("action"))


# ---------------------------------------------------------------------------
# Feeds: RSS, Atom and JSON Feed.
# ---------------------------------------------------------------------------

_TAG = re.compile(r"<[^>]+>")


def _text(value: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(_TAG.sub("", value or ""))).strip()


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def parse_feed(raw: bytes, limit: int = 12) -> list:
    """Headlines from whatever a news source publishes.

    RSS, Atom and JSON Feed between them cover every news site and every feed
    bridge, which is also the only realistic way to put an X account on a
    television: X's own API is paid, and a bridge that turns an account into a
    feed is a URL like any other.
    """
    raw = (raw or b"").strip()
    if raw.startswith(b"{"):
        try:
            items = json.loads(raw).get("items") or []
        except ValueError as exc:
            raise SourceError("that feed is not readable JSON") from exc
        titles = [_text(i.get("title") or i.get("content_text") or "")
                  for i in items]
        return [t for t in titles if t][:limit]
    try:
        root = ET.fromstring(raw)
    except ET.ParseError as exc:
        raise SourceError("that address is not a feed") from exc
    titles = []
    for element in root.iter():
        if _local(element.tag) in ("item", "entry"):
            for child in element:
                if _local(child.tag) == "title":
                    titles.append(_text(child.text or ""))
                    break
    return [t for t in titles if t][:limit]


def feed(url: str, limit: int = 12) -> list:
    return parse_feed(_get(url, {"User-Agent": BROWSER}), limit)


# ---------------------------------------------------------------------------
# When a bar may show.
# ---------------------------------------------------------------------------

DAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]


def in_window(window: str, now: dt.datetime) -> bool:
    """Whether a local time falls in a window such as "07:00-09:30".

    A window that ends before it starts runs past midnight, so "22:00-02:00"
    is late evening into the small hours rather than never.
    """
    m = re.match(r"^\s*(\d{1,2}):(\d{2})\s*-\s*(\d{1,2}):(\d{2})\s*$", window or "")
    if not m:
        return False
    start = int(m.group(1)) * 60 + int(m.group(2))
    end = int(m.group(3)) * 60 + int(m.group(4))
    minutes = now.hour * 60 + now.minute
    if start == end:
        return True
    if start < end:
        return start <= minutes < end
    return minutes >= start or minutes < end


def on_day(days: list, now: dt.datetime) -> bool:
    return not days or DAYS[now.weekday()] in [d[:3].lower() for d in days]


def should_show(bar: dict, now: dt.datetime, facts: dict) -> bool:
    """The whole schedule rule for one bar.

    facts carries what the service already knows, so this stays a pure
    decision: market is "open" or "closed", live is whether games are on.
    """
    if not bar.get("enabled"):
        return False
    when = bar.get("when", "always")
    if not on_day(bar.get("days") or [], now):
        return False
    if when == "always":
        return True
    if when == "market":
        return facts.get("market") == "open"
    if when == "live":
        return bool(facts.get("live"))
    if when == "window":
        return in_window(bar.get("window", ""), now)
    return False
