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

## What is missing

HDMI-CEC, which is what makes an ordinary TV remote drive the box over the
HDMI cable itself, needs `plasma-remotecontrollers`. Fedora does not package
it, so it needs building from source. `libcec` is installed and ready for it.
Until then a Bluetooth remote or keyboard pairs normally through **System
Settings**, and Bigscreen already maps d-pad and media keys.
