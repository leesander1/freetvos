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

A USB or PCIe tuner plugged into the box itself works too, as an option: see
below.

## A tuner in this box

**Sources**, then **Tuner in this box**. It is off until switched on, and until
then nothing about it runs.

Switching it on starts TVHeadend, which does the tuning, the channel scan and
the guide read from the broadcast. It listens on the box itself and nowhere else,
so there is no login to set up. Then choose how the signal arrives, and the
nearest transmitter or frequency plan, and it scans:

| Choice | Where |
|---|---|
| Antenna | United States, Canada, Mexico, South Korea |
| Cable | United States |
| Antenna | Europe, Australia, most of Asia and Africa |
| Cable | Europe |
| Antenna | Japan, Brazil and most of South America |

A scan takes several minutes and can be left running. When it finishes, the
tuner's channels are in the guide with everything else, and the guide comes from
the broadcast itself.

Satellite is not offered: a dish needs its LNB and switch described before a scan
means anything, which is not a question for a remote.

### Which tuners work

Any tuner Linux has a driver for. The common ones are already in the image,
including Hauppauge WinTV, PCTV, and Realtek based USB sticks, and the firmware
many of them load is installed too. The choice to use it is kept across
restarts.

### What has been checked

Everything except a tuner. There is none in the VM and the kernel's virtual tuner
is not built for this kernel. Checked on the device: TVHeadend starting and
answering, and its channel list and guide reaching Live TV after a scan run
against a playlist in place of a tuner. Checked against TVHeadend itself:
choosing a US antenna plan creates the network's 68 frequencies ready to scan.
Not checked: attaching a real tuner to that network and receiving a channel.

Two things the first device run found. TVHeadend turns what a scan finds into
channels a few seconds after the scan ends, not during it, so the scan first
reported "0 channels" for a list that had three; it now waits for them. And only
what the new scan found is turned into channels, so scanning a second time, or
for a second kind of signal, leaves the first network's channels as they were.

TVHeadend brings in the HDHomeRun configuration program, which added a desktop
tool to the home screen. It is hidden.

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
