# Tickers

Bars along the bottom of the screen that stay on top of whatever is playing:
stock prices, live scores, and one you fill yourself. Each can be switched on
alone or stacked with the others, and each has its own schedule.

## The three bars

- **Stock prices.** The symbols you choose, with the price and the day's move in
  green or red.
- **Live scores.** Games from the leagues followed in Scores, live ones marked in
  green, teams you follow starred.
- **Your own bar.** A title, an optional logo, a message, and headlines from any
  news feed: RSS, Atom or JSON Feed.

Each bar crawls its items end to end without a gap, however short the list, so
six stocks fill the bar as well as forty headlines do.

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

## Choosing stocks

**Tickers**, then **Choose stocks**. Your stocks are listed in the order they
scroll: Enter removes one, left and right move it earlier or later. Search finds
a company by name or symbol with the on-screen keyboard, and the popular list
adds the usual ones in a press.

Search leaves out the structured notes and mutual funds that clutter Nasdaq's
own results, so searching "tesla" finds Tesla rather than a page of barrier
notes linked to it.

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

## X and Twitter

X has no free API, so there is no built-in X source. An account can still be
shown through any service that turns it into an RSS feed, entered as the news
feed address like any other.

## From a terminal

```bash
freetvos-bars status
freetvos-bars on stocks
freetvos-bars off sports
freetvos-bars settings
```
