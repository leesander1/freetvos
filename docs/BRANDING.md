# Rebranding FreeTVOS

Everything below was read out of the built image, not from documentation, so
the paths and current values are what this image actually ships today.

## What a viewer sees, in order, from power-on

Six branded surfaces sit between the power button and the home screen. Five of
them currently say Fedora or KDE.

| # | Surface | Currently | Controlled by |
|---|---|---|---|
| 1 | GRUB menu | "Fedora Linux 44 (Forty Four) (ostree:0)" | `NAME` in os-release, read at deployment time |
| 2 | Boot splash | `bgrt` theme, shows the firmware vendor logo | Plymouth default theme |
| 3 | Login | SDDM theme `01-breeze-fedora` | `Current=` in the SDDM config |
| 4 | Session splash | KDE and Plasma logos | look-and-feel `org.kde.plasma.bigscreen` |
| 5 | Wallpaper | Fedora `Next` | look-and-feel default |
| 6 | About screen | "Fedora Linux 44", Fedora logo | `PRETTY_NAME` and `LOGO` in os-release |

A television is judged on the first ten seconds. Surfaces 2 and 4 are the ones
a viewer actually stares at, so they matter most; surface 3 flashes past in
under a second because autologin is on.

## 1. os-release

The cheapest change with the widest reach. GRUB entries, the About screen, and
several toolkits all read it.

Write `/usr/lib/os-release` in the overlay, keeping `ID=fedora` and adding
`ID_LIKE`, because dnf repository logic and third-party installers key off it.
Changing `ID` outright will break package installs.

```
NAME="FreeTVOS"
ID=freetvos
ID_LIKE="fedora"
VERSION_ID=0.1.0
PRETTY_NAME="FreeTVOS 0.1.0"
LOGO=freetvos
HOME_URL="..."
VARIANT="Television"
VARIANT_ID=tv
```

`LOGO=freetvos` resolves through the icon theme, so it needs the icon set in
`ASSETS.md` §1 installed under `hicolor`.

## 2. Plymouth boot splash

The image currently defaults to `bgrt`, which draws whatever logo the firmware
advertises. On a TV box that is usually the board vendor's, or nothing at all.

Create `/usr/share/plymouth/themes/freetvos/` by copying the structure of the
stock `spinner` theme, which is the right base: it is script-driven and already
handles arbitrary resolutions. Then set it as default in the Containerfile and
regenerate the initramfs, or the change will not appear at boot.

Assets, matching the stock theme's own geometry:

| File | Size | Count | Notes |
|---|---|---|---|
| `animation-%04d.png` | 32x32 | 36 frames | The spinner; sizes verified from the stock theme |
| `watermark.png` | 149x43 | 1 | Corner mark. Can be larger, but keep the aspect |
| `bullet.png` | 10x10 | 1 | Progress dot |
| `header-image.png` | 640x640 | 1 | Optional centred logo, see `ASSETS.md` §2 |

## 3. SDDM

Autologin means this appears for well under a second, so it is the lowest
priority of the six. The cheapest acceptable result is a theme that draws a
flat `BRAND_BG` field with no text at all, which reads as part of the boot
sequence rather than a login screen that flashed by.

Set `Current=freetvos` in `/usr/lib/sddm/sddm.conf.d/10-freetvos.conf`, next to
the autologin block already there, and add
`/usr/share/sddm/themes/freetvos/`.

## 4. Session splash

This is the one worth spending effort on. It is on screen for several seconds
on modest hardware.

**Done**, and not the way first planned. `org.freetvos.bigscreen` carries a
splash, but selecting it does nothing: the Bigscreen session pins its own
look-and-feel, `org.kde.plasma.bigscreen`, in a locked setting, and Plasma
copies that package's splash choice into the viewer's `kdedefaults`, which
outranks `/etc/xdg`. A `ksplashrc` there was read and ignored, and the KDE and
Plasma logos kept showing. Swapping the whole look-and-feel would also swap the
home screen's layout, which the FreeTVOS package does not carry.

So the build replaces the `contents/splash` directory inside Bigscreen's own
package with FreeTVOS's. Whichever package Plasma picks, it draws the FreeTVOS
mark on the brand ground. The FreeTVOS package also declares
`KPackageStructure`, which Plasma 6 expects in place of `ServiceTypes`.

The boot splash, surface 2, needed the initramfs rebuilt in the image: Plymouth
starts inside it, and the base image's was built before the FreeTVOS theme
existed, so early boot showed Fedora's theme. An installed system also needs
`quiet splash` on its kernel command line for Plymouth to draw at all; the
installer ISO now sets it.

Consider dropping the busy spinner entirely. Apple TV and Roku both show a
static mark, and a still logo reads as faster than an animated one because
there is no motion to measure the wait against.

## 5. Wallpaper

Set in the look-and-feel package's `defaults` file. See `ASSETS.md` §3 for
sizes and the caution about contrast behind the focus ring.

## Colours: the FreeTVOS scheme

`/usr/share/color-schemes/FreeTVOS.colors` is Breeze Dark with every colour
swapped for the brand palette FreeTVOS's own pages use: `#0B0E14` background,
`#151A23` surfaces, `#E6EAF2` text, and `#3DDC97` for every highlight, focus and
hover in place of Breeze's blue. The frame around the selected app tile, the
focused row in Bigscreen's settings and every KDE dialog take their colours
from it.

Plasma reads colours from three places, and each once kept Breeze blue, so the
build (`tune-shell-defaults.py`) fills all three from the one file:

| Where | Why it matters |
|---|---|
| `/etc/xdg/kdeglobals` | The system default; the scheme's colours are merged in, since the `ColorScheme` key alone is only a label |
| Bigscreen's look-and-feel `defaults` | Names a scheme that Plasma copies into `kdedefaults`, which outranks `/etc/xdg`; it named Breeze Dark |
| The breeze-dark Plasma theme's `colors` | The shell draws with the Plasma theme, which carries its own colours rather than following the system |

Writing on a selected row is dark, because white on `#3DDC97` is not legible.
A filled highlight elsewhere needs no entry: KDE tints the background with the
accent, which comes out `#0F3023`, and white reads on that. `tools/test-theme.py`
checks all of it.

## 6. Removing rather than rebranding

Two things are better deleted than restyled.

**KDE's own onboarding.** `plasma-welcome` is already removed in the
Containerfile; it opened a desktop wizard over the TV interface.

**The double splash.** Plymouth hands over to SDDM which hands over to the
Plasma splash, so a viewer sees three separate loading screens. The usual fix
is to keep Plymouth running until the session is actually up, so the boot looks
like one continuous animation rather than three. This is configuration, not
artwork, and is worth doing before any of it is drawn.

## Order of work

1. os-release, since it costs nothing and fixes the GRUB entry and About screen
2. The triple-splash handover, which is structural and changes what art is even needed
3. Session splash artwork
4. Plymouth theme
5. Wallpaper
6. SDDM theme, last and least
