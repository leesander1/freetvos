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

## Attempted, and where it stopped

The controller is written and half of it works. `freetvos-split list` correctly
identifies the service windows and their process ids, filtering out the
Chromium helper processes that inherit the same command line. The audio side is
sound: each pane is its own Chromium process, so streams are matched on
`application.process.id` rather than application name, which is "Chromium" for
all of them.

The tiling does not work. KWin accepts the script over DBus, `loadScript`
returns an id and `start` returns cleanly, and nothing happens. A probe script
that only minimised windows had no effect either, so the scripts are being
loaded and never executed. Nothing appears in KWin's log.

The likely cause is that KWin 6 no longer runs scripts injected this way, and
wants a proper installed script package listed in kwinrc's `[Plugins]` section
instead. That is the next thing to try, and it changes the shape of the
solution: the script becomes part of the image and stays resident, reacting to
a DBus signal rather than being loaded per invocation.

Two other findings worth keeping:

- **Meta is taken.** Pressing it opens Bigscreen's home overlay, so Meta chords
  collide with the shell. The bindings moved to Ctrl+Alt.
- **KWin's own quick-tile shortcuts are not registered** in this session, so the
  usual manual fallback of tiling each window by hand is not available either.

## Suggested order

1. Two-pane side by side, with audio following focus. This is the whole idea in
   its smallest useful form and proves the audio routing, which is the risky
   part.
2. A focus indicator and the remote binding to switch panes.
3. Four-pane quarters, gated on measuring decode headroom on real hardware.
4. UVC capture as a pane, once the grid is stable.
