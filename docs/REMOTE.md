# Using a phone as the remote

Three separate mechanisms ship in the image, and they do different jobs. Most
people will want the first.

## 1. KDE Connect, for full control

Already installed and enabled. This is the one that behaves like a remote:
a trackpad, a keyboard for typing into search boxes, volume, and media
transport controls that work with whatever is playing.

On the television, open **KDE Connect** from the home screen. On the phone,
install KDE Connect (Android, via F-Droid or Play) or KDE Connect iOS, put both
devices on the same network, and pair. The TV must accept the pairing request.

Once paired the phone offers a **Remote input** pad and **Multimedia control**.
Typing is the part that matters most: entering a password or a search term with
a d-pad is miserable, and the phone keyboard makes it ordinary.

Ports are 1714 to 1764, TCP and UDP. Both devices must be on the same subnet;
KDE Connect does not traverse subnets or guest-network isolation.

## 2. DIAL, for launching from the YouTube app

The receiver runs as `freetvos-dial.service`. Open YouTube on the phone, tap
cast, and the television appears. The phone then drives what plays.

This is not Chromecast and does not mirror the phone. DIAL only tells the TV
which app to open and hands it a pairing code; the television then streams the
content itself. That is also why it costs the phone no battery.

Netflix's app speaks DIAL too and is wired up, though it is less reliable than
YouTube's.

## 3. AirPlay, for mirroring from an iPhone or Mac

`freetvos-airplay.service` runs UxPlay, advertised as **FreeTVOS** in the iOS
and macOS AirPlay picker. This one genuinely mirrors the screen and streams
audio, so it is the right choice for showing photos or anything with no TV app
of its own.

## Getting back out of an application

Every service opens fullscreen without decoration, so there is no visible exit.
**Back** and **Home** on a remote both close whatever is on top, which reveals
the home screen underneath. On a keyboard that is Meta+Backspace.

These are bound in `/etc/xdg/kglobalshortcutsrc` to the `XF86Back` and
`XF86HomePage` keysyms that remotes and HDMI-CEC emit. They have not been
tested against a real remote, because the development VM has neither CEC nor an
infrared receiver.

## None of this works in the development VM

Worth knowing before concluding something is broken. KDE Connect, AirPlay and
DIAL all need the television to be reachable on the same local network as the
phone. QEMU's default user-mode networking puts the guest behind a NAT at
10.0.2.15 where nothing on the real network can reach it, and KDE Connect's
discovery is a UDP broadcast that does not cross it.

The daemon runs and listens on 1716 in the VM, so it looks healthy from inside
and is undiscoverable from outside. Bridged networking would fix it, but the
Homebrew QEMU build has no vmnet backends compiled in, so it is not available
on this host at all.

These three features can only be tested on real hardware.

## HDMI-CEC, so the TV's own remote drives the box

Already present, and enabled. This was previously recorded here as needing a
source build of plasma-remotecontrollers; that was wrong. The standalone
project is gone from KDE and its job moved into
`plasma-bigscreen-inputhandler`, which ships with the shell, links libcec and
starts with the session.

Check it with:

```bash
freetvos-cec status
```

In the development VM that reports CEC enabled and no adapter present, which is
correct: there is no HDMI at all. On real hardware it should find `/dev/cec0`.
Two things to check if it does not:

- CEC must be enabled in the television's own settings, where it is rarely
  called CEC. Look for Anynet+, Bravia Sync, SimpLink, Viera Link or AQUOS Link.
- Not every HDMI port carries CEC, and not every cable connects the pin.

The box also asks the television to switch to its input at login, the way a
games console does, so it does not boot to whatever input was left selected.
`freetvos-cec claim` does it by hand.

None of this has been tested against a real television.

## What is missing

Nothing in the remote path, as far as can be told without hardware. What
remains is choosing which remote keys drive split view: those shortcuts are on
Ctrl+Alt chords that no remote sends, and Meta is taken by the home overlay.
Picking real keysyms needs a remote to press.
