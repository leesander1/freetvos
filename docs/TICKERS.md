# Tickers

Bars along the bottom of the screen that stay on top of whatever is playing:
stock prices, live scores, and as many bars of your own as you like. Each can be
switched on alone or with the others, and each has its own schedule. They stack
one above another, or share a single bar and take turns, at full size or thin.

Everything here is set from **Tickers** on the home screen. The same settings
live in a file, described at the end, for anyone who would rather write them.

## The bars

- **Stock prices.** The symbols you choose, with the price and the day's move in
  green or red.
- **Live scores.** Games from the leagues followed in Scores, live ones marked in
  green, teams you follow starred.
- **Your own bars.** A title, a logo, a message, a colour, and a feed of your
  choosing: a news site's headlines, a file on the television, or numbers of your
  own. **Add another bar of your own** at the bottom of the page makes another,
  and **Remove this bar** takes an extra one away.

Each bar crawls its items end to end without a gap, however short the list, so
six stocks fill the bar as well as forty headlines do.

## How they look

At the top of the Tickers page, for every bar at once.

| Setting | Choices |
|---|---|
| Size | **Full**, about 6% of the screen's height a bar, or **Thin**, a little over half that. The writing scales with the bar. |
| Layout | **Stacked**, every bar that is showing at once, or **One bar, taking turns**: a single bar that moves to the next one on a timer. |
| Next bar | With taking turns: every 15, 20 or 30 seconds, or every minute. |

Taking turns only rotates between bars that are showing at the time. A scores bar
that waits for a live game is left out of the turns until there is one.

## When they show

| Choice | Stocks | Scores | Your own |
|---|---|---|---|
| Always | yes | yes | yes |
| While the market is open | yes | | |
| While games are live | | yes | |
| At set hours | yes | yes | yes |

Any of them can also be limited to weekdays or weekends. A bar with nothing to
show draws nothing at all, rather than an empty strip across a film.

"While the market is open" asks Nasdaq, which knows about holidays and early
closes. If Nasdaq cannot be reached it falls back to the clock, 9:30 to 4 on a
weekday in New York, which is right except on exchange holidays.

## Your own bars

| Setting | What it does |
|---|---|
| Title | The label on the left, in capitals by convention: `ACME`, `NEWS` |
| Message | One line that leads the crawl, before anything from the feed |
| Logo | A picture beside the title: a web address, or a file on the television |
| Feed | Where the rest of the items come from; see below |
| Colour | The label's background and the line along the top, as `#RRGGBB`, for example `#3DDC97` |
| Speed | Slow, normal or fast |

A bar needs a message, a feed, or both. With neither it has nothing to show and
stays off.

### What a feed can be

The feed setting takes a web address or a file on the television, and reads any
of these:

**A news feed**: RSS, Atom or JSON Feed. Each headline becomes an item. Nearly
every news site publishes one; look for "RSS" on the site, or try adding `/feed`
or `/rss` to its address.

```
https://feeds.bbci.co.uk/news/rss.xml
```

**FreeTVOS ticker JSON**, for numbers of your own. Items are drawn the way
prices are: a label, then a value, then a change in green or red.

```json
{
  "items": [
    { "label": "Sales today", "value": "$12,400", "change": "4.2%", "direction": "up" },
    { "label": "Open tickets", "value": "18", "change": "3", "direction": "down" },
    { "label": "Top store", "value": "Leeds", "star": true },
    { "label": "Canteen opens at noon" }
  ]
}
```

| Field | Required | Meaning |
|---|---|---|
| `label` | yes | The first thing shown for the item. Items without one are left out |
| `value` | no | Shown after the label, like a price |
| `change` | no | Shown after the value, smaller |
| `direction` | no | `up` and `live` draw the change in green, `down` in red, `flat` in grey. The default is `flat`; anything else is treated as `flat` |
| `star` | no | `true` puts a star before the label |

A bare list, `[{ "label": ... }, ...]`, works as well as the object form. Labels
are cut at 120 characters, and values and changes at 40, rather than refused.

**Plain text**, one item a line. The simplest thing to keep in a file:

```
Welcome to ACME
Fire drill at 3 this afternoon
The car park closes at 7
```

HTML pages are refused rather than shown as markup crawling past.

### A file on the television

Give the feed as a path, `/var/home/tv/board.txt`, or as `file:///var/home/tv/board.txt`.
Whatever writes that file, a script, a shared folder, another program, the bar
picks the change up on its next refresh. Up to one megabyte is read.

### How often a feed is read

A custom bar asks its feed every ten minutes while the bar could be showing,
prices every minute, scores every thirty seconds. A feed that fails keeps the
last good items on screen rather than blanking the bar; the reason shows under
the bar's name on the Tickers page.

### X and Twitter

X has no free API, so there is no built-in X source. An account can still be
shown through any service that turns it into an RSS feed, entered as the feed
like any other.

## Choosing stocks

**Tickers**, then **Choose stocks**. Your stocks are listed in the order they
scroll: Enter removes one, left and right move it earlier or later. Search finds
a company by name or symbol with the on-screen keyboard, and the popular list
adds the usual ones in a press.

Search leaves out the structured notes and mutual funds that clutter Nasdaq's
own results, so searching "tesla" finds Tesla rather than a page of barrier
notes linked to it.

## The settings file

Everything on the Tickers page is kept in `~/.config/freetvos/bars.json`, which
for the television's own account is `/var/home/tv/.config/freetvos/bars.json`.
The service reads it every ten seconds, so an edit shows without restarting
anything. Bars are listed top first:

```json
{
  "size": "thin",
  "layout": "rotate",
  "rotate_every": 20,
  "bars": [
    { "id": "custom", "kind": "custom", "enabled": true, "when": "always",
      "title": "ACME", "message": "Welcome to ACME",
      "logo": "/var/home/tv/acme.png", "feed": "/var/home/tv/board.json",
      "accent": "#E4002B", "speed": 120, "window": "", "days": [] },
    { "id": "stocks", "kind": "stocks", "enabled": true, "when": "market",
      "symbols": ["SPY", "AAPL", "NVDA"] },
    { "id": "sports", "kind": "sports", "enabled": false, "when": "live" },
    { "id": "custom-2", "kind": "custom", "enabled": true, "when": "window",
      "window": "17:00-23:00", "days": ["sat", "sun"],
      "title": "NEWS", "feed": "https://feeds.bbci.co.uk/news/rss.xml" }
  ]
}
```

| Key | Values |
|---|---|
| `size` | `full` or `thin` |
| `layout` | `stacked` or `rotate` |
| `rotate_every` | Seconds per bar when taking turns, 5 to 600 |
| `id` | Any unique name. The first bar of each kind is named after the kind |
| `kind` | `stocks`, `sports` or `custom`. One stocks bar and one scores bar; custom bars as many as you like |
| `when` | `always`, `market` (stocks), `live` (scores) or `window` |
| `window` | With `window`: `HH:MM-HH:MM`. One that ends before it starts runs past midnight |
| `days` | Empty for every day, or some of `mon` `tue` `wed` `thu` `fri` `sat` `sun` |
| `speed` | Crawl speed in pixels a second: 80 slow, 140 normal, 220 fast |

Anything left out takes its default. A file written before custom bars could be
repeated, with no `kind` keys, still reads.

## How it is drawn

The bars are a small QML program in the compositor's overlay layer, the layer
above fullscreen windows. It takes no keyboard focus, so the remote keeps
working whatever is playing, and split view leaves it alone because it is not an
ordinary window. A service in the session decides which bars should show and
fetches their data; the overlay only draws what it is handed, and is not running
at all while every bar is off.

Pages drawn by this system scroll the highlighted row to the middle of the
screen, so a stack of bars never covers the row you are on.

## Where the numbers come from

Prices, search and market hours come from Nasdaq's public site API; scores from
ESPN's scoreboard feed, as in Scores. Both need no key and no account, and both
are undocumented. A failed refresh keeps the last good prices on screen rather
than blanking the bar.

## From a terminal

```bash
freetvos-bars status                  # what is showing, and why not
freetvos-bars on stocks               # any bar by its id
freetvos-bars off custom-2
freetvos-bars add                     # another bar of your own; prints its id
freetvos-bars size thin               # or full
freetvos-bars layout rotate 30        # one bar, 30 seconds each
freetvos-bars layout stacked
freetvos-bars settings                # the page itself
```
