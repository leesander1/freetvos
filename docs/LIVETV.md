# Live TV

Channels you flip through with a remote, and a guide of what is on, from
whatever serves live TV on your network.

## What it works with

| Source | How to add it |
|---|---|
| Tunarr | Its address, such as `tunarr.lan`. Port 8000 is assumed |
| ErsatzTV, TVHeadend, Threadfin, IPTV | A playlist address, and a guide address if the playlist does not name one |
| HDHomeRun tuners, or anything pretending to be one | Its address |

Tunarr turns a Plex or Jellyfin library into scheduled channels. It publishes
them as an M3U playlist at `/api/channels.m3u` with an XMLTV guide at
`/api/xmltv.xml`, and also pretends to be an HDHomeRun tuner. Either door works.

A tuner card plugged into this box directly is not supported. That needs
TVHeadend running here, which it is not; run TVHeadend on another machine and add
it by playlist instead.

## The guide

Channels down the side, time across the top, with a line where now is. Up and
down change channel, left and right move through time, and moving between
channels keeps the same moment in time rather than the same column. Enter
watches. Up from the top reaches **Sources**, where Tunarr, a tuner or a playlist
is added with the on-screen keyboard.

## Watching

| Key | Does |
|---|---|
| Up, Right, Channel up | Next channel |
| Down, Left, Channel down | Previous channel |
| Digits | Go straight to that channel |
| Enter | What is on now and next |
| Menu, G | Back to the guide |
| Back | Leave |

Every change of channel shows the number, the name, what is on until when, and
what is next, at the top of the screen where the tickers cannot cover it. The
last channel watched is where it starts next time.

## When a server goes away

The channel list is cached. If the server cannot be reached, the last list stays
on screen with a note saying so, rather than an empty guide.

## Trying it without a server

`tools/pretend-tunarr.py` serves three looping test channels and a guide written
around the current time, on the same paths Tunarr uses. From the VM, the Mac is
at `10.0.2.2`:

```bash
python3 tools/pretend-tunarr.py --make-channels
freetvos-livetv add-tunarr 10.0.2.2:8951
```

## From a terminal

```bash
freetvos-livetv channels
freetvos-livetv watch 7
freetvos-livetv sources
freetvos-livetv add-m3u http://tv.lan/playlist.m3u --guide http://tv.lan/guide.xml
```
