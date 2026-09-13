# Scores

**Scores** on the home screen shows every game in the leagues you follow, on one
page, live ones first, with the teams you follow above everything else. It
refreshes itself every twenty-five seconds. A score that needs a button press is
not a score.

Each card carries both teams with their logo, ranking and record, the score, the
clock, and what is happening right now: the down and distance in football, the
count in baseball. Enter opens a game for the venue, the broadcaster, the last
play, and a button to follow either team.

## Leagues

NFL, College Football, NBA, WNBA, men's and women's College Basketball, MLB,
NHL, MLS, the Premier League and the Champions League. NFL, College Football and
NBA are followed to begin with, because a page with nothing on it is not a
useful first impression. **Choose leagues** changes that.

## Following a team

**Follow teams**, then a league, then the team. Its games sort above everything
else and carry a star. This is the whole point of the page: on a Saturday there
are forty college football games and you care about one of them.

## Where the numbers come from

ESPN's public scoreboard feed. It needs no key and no account. It is also
undocumented, and that is worth saying plainly: it is what every score widget on
the internet is built on, it has been steady for years, and nobody has promised
it will keep its shape. Everything that reads it is defensive for that reason. A
field that moves costs a blank line on a card rather than a page that will not
load, and a league that cannot be reached costs that league's cards rather than
the page.

Apple Sports has no public interface at all, so it was never an option, however
much this page owes to it.

### One thing that will look like a bug later

No `User-Agent` header is sent, and that is deliberate. ESPN's edge answers a
plain scripting agent, which is what Python sends when nothing is set, and
returns 403 both to a made-up product name and to a full browser string. The
same code stopped working the moment it introduced itself. Adding a polite
`User-Agent` back will break this, and it will break it everywhere at once.

## From a terminal

```bash
freetvos-sports scores
freetvos-sports scores --league ncaaf
freetvos-sports scores --date 20260913
freetvos-sports leagues
freetvos-sports follow nhl mlb
freetvos-sports teams nfl
freetvos-sports follow-team nfl 12
```

## Not built

No standings, no schedules beyond what today's scoreboard returns, and no
notifications when a followed team starts or scores. Notifications are the
obvious next one and need somewhere to put them: this shell draws nothing for a
desktop notification, which is the same wall the external-input work hit.
