# Split view: watching two or four things at once

Not built. This is the design, the hard part, and an honest estimate, so the
decision to build it can be made with the costs visible.

## What the pieces would be

**Window layout.** KWin is a scriptable compositor, and a KWin script can place
and resize windows on a grid without touching the applications themselves. Each
service already runs as its own Chromium window with a distinct window class
(`freetvos-netflix` and so on), set by the launcher, so a script can address
them individually. This part is straightforward.

**Audio focus.** This is the feature's real substance and the reason it is
worth building rather than just tiling windows. PipeWire exposes every playing
stream separately, so the focused pane can hold full volume while the others
are muted or ducked, and switching focus moves the audio with it. `wpctl` can
set per-stream volume from a script today.

**Input focus.** Only the focused pane should receive d-pad and media keys, or
a press meant for one service will reach another. KWin controls this, but it
has to be kept in step with the audio focus or the two disagree and the result
feels broken.

**A layout switcher.** A key on the remote to cycle single, side-by-side, and
quarters, plus a focus indicator visible from three metres away. Without an
obvious focus ring, a viewer cannot tell which pane will respond to them.

## The hard part

Not the tiling. It is that **each pane costs a full Chromium process with its
own video decode**, and DRM makes this worse. A device that plays one 720p
stream comfortably can fall over on four, and if hardware decode is unavailable
the software decoder will saturate every core. Four DRM panes also mean four
concurrent Widevine sessions, and some services limit concurrent streams per
account regardless of the device.

The realistic shape is two panes on decent hardware, four only with hardware
decode and modest sources.

## HDMI inputs alongside apps

Worth knowing: `org.kde.plasma.bigscreen.uvcviewer` is already installed and
already on the home screen. It displays a UVC video device, so a USB HDMI
capture stick appears as just another window and would tile in the same grid as
the apps. That makes "a game console in one pane, a stream in the other"
achievable without any new video plumbing, which is the expensive part.

Latency is the caveat. USB capture adds enough delay to be noticeable, so this
suits watching rather than playing.

## How to use it

**Split View** in Applications asks on screen which service goes in each pane,
then opens and tiles them. It works from a standing start, rather than assuming
the viewer already knew to open two services first.

The picker is a page served over localhost rather than a native dialog. The
services are web apps already, so a page inherits the same d-pad handling and
the same look, and it can show the services' own icons without a toolkit.

Ticking **Save as a quick launch tile** on the confirmation step creates a tile
that reopens that pair in one action, with an icon composed from the two
services' own icons so the pairing is legible on the grid.

The same tiles can be made from a shell:

```bash
freetvos-combo add --apps "plex youtube"
```

`--name`, `--layout` and `--icon` override the defaults; `freetvos-combo list`
and `remove` manage them.

From a keyboard: Ctrl+Alt+2 for two panes, Ctrl+Alt+4 for four, Ctrl+Alt+1 to
go back to one, Ctrl+Alt+Tab to move focus. No remote sends these, and Meta is
unavailable because it opens the home overlay, so choosing remote keys needs
real hardware to test against.

The focused pane is outlined in the accent colour, and the sound follows it.

## What it took, and three bugs worth remembering

**KWin ignores scripts injected over DBus.** loadScript returns an id, start
returns cleanly, and nothing runs. The script has to be installed as a package
and enabled in kwinrc, which also lets it register its own shortcuts.

**Chromium's --class is not the Wayland app id.** Filtering windows on
resourceClass starting with freetvos- matched nothing. Every normal window is
taken instead, which is also more correct here: the shell is not a normal
window, so the only normal windows are the services.

**Chromium rewrites its process title.** /proc/PID/cmdline is one
space-separated blob with no NUL separators, so splitting on NUL gives a single
line: an unanchored grep returns the whole command line as the "class", and an
anchored one never matches. The token has to be extracted with a regex.

The focus indicator is drawn by the bundled browser extension, not the
compositor. The only appearance a KWin script can change is opacity, and
dimming the pane you are not watching defeats the point of showing two.

## Suggested order

1. Two-pane side by side, with audio following focus. This is the whole idea in
   its smallest useful form and proves the audio routing, which is the risky
   part.
2. A focus indicator and the remote binding to switch panes.
3. Four-pane quarters, gated on measuring decode headroom on real hardware.
4. UVC capture as a pane, once the grid is stable.
