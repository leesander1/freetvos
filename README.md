# FreeTVOS

A free open television operating system that won't track you. Built on KDE Plasma Bigscreen, defined as a
bootable container and shipped as an atomically updatable image.

**Status**: working / WIP 

boots to a branded Bigscreen home screen in QEMU on Apple Silicon, with
twelve streaming services, live scores, stock and score tickers, Live TV with a
guide, split view and picture in picture, video calls, external inputs, your own
media, and a first-run setup wizard. Built for x86_64 but not yet installed on
real hardware.

![Moving around FreeTVOS with a remote: the home screen, live scores, one game, the app catalogue, external inputs, and YouTube beside ESPN+ in split view](docs/images/demo.gif)

## Why
- Free open source completely customizable experience
- No analytics or data collection of any kind
- Freedom to own the glass

## Features

Every picture here is the television's own framebuffer, taken through the
hypervisor while the VM runs, not a mockup. `python3 tools/showcase.py stills`
and `python3 tools/showcase.py demo` take them again.

| | |
|---|---|
| ![The home screen](docs/images/home.png) | ![The first-run wizard](docs/images/setup.png) |
| **Home.** Twelve streaming services and every feature, on Plasma Bigscreen. | **Setup Wizard.** Opens by itself the first time the television is turned on. |
| ![Typing a wifi password on screen](docs/images/setup-keyboard.png) | ![The app catalogue](docs/images/apps.png) |
| **Typing with a remote.** The page draws its own keyboard. The network names are stand-ins, as the VM has no radio. | **Customizable Apps/Services.** Seventeen more services a press away, or any site by its address. |
| ![Live scores](docs/images/scores.png) | ![One game](docs/images/scores-game.png) |
| **Sports App.** Live games first, refreshing on their own, with the teams you follow above everything. | **Sports Game Details.** The clock, the down and distance, the last play, and a button to follow either side. |
| ![Your own media](docs/images/library.png) | ![External inputs](docs/images/inputs.png) |
| **Library.** A USB drive, a Plex server or a Jellyfin server, and where you left off. | **Inputs/USB HDMI Device Passthrough.** A console or set-top box through a USB HDMI capture device. This is good for if you don't have a device with a way to plug device directly into the screen. |
| ![Picture and sound settings](docs/images/picture-sound.png) | ![Choosing what goes in split view](docs/images/split-picker.png) |
| **Picture & Sound.** Resolution, overscan, output, volume and Bluetooth, laid out for a remote. | **Split view.** Two services side by side, with the sound following the one in focus. |
| ![Stock, score and news bars on the home screen](docs/images/tickers-home.png) | ![The Tickers settings](docs/images/tickers.png) |
| **Tickers.** Stock prices, live scores and your own headlines, stacked above whatever is playing. | **Each on its own schedule.** Always, while the market is open, while games are live, or at set hours. |
| ![Choosing stocks for the ticker](docs/images/stock-picker.png) | ![Picture in picture](docs/images/pip.png) |
| **Choosing stocks.** Search by company, pick from the popular list, and put them in order. | **Picture in picture.** One service full screen and another small in the corner. |
| ![The Live TV guide](docs/images/livetv-guide.png) | ![Watching a Live TV channel](docs/images/livetv-watching.png) |
| **Live TV.** A programme guide from Tunarr, an HDHomeRun tuner or a playlist. Full support for USB tuner. The channels here are test patterns. | **Changing channel.** The number, what is on, and what is next. |
| ![Joining a video call](docs/images/meetings.png) | ![Pinning a show to the home screen](docs/images/pin.png) |
| **Meetings.** Zoom, Meet and Teams, joined by meeting ID and passcode with the remote. USB camera support. | **Pin to the home screen.** The favourites key, or P, over whatever is playing puts it on the home screen with its poster. |

## Why it is built this way

The entire OS is a `Containerfile`. `podman build` produces it, and
`bootc-image-builder` turns that same image into a qcow2 for a VM, a raw image
for an SD card, or an installer ISO. Updates are atomic with rollback, which a
set-top box needs and a package manager cannot provide: a television that fails
to boot after an update is a brick in someone's living room.

## Quick start

```bash
make build && make disk && make run
```

That builds the image, produces `output/qcow2/disk.qcow2`, and boots it in a
window. `HEADLESS=1 make run` swaps the window for a serial log, and
`tools/screenshot.sh` captures the screen through QEMU's monitor.

The VM comes up with ssh on port 2222, using the public key of whoever ran the
build.

```bash
ssh -p 2222 tv@localhost
```

## Layout

| Path | What it is |
|---|---|
| `brand/brand.env` | Product name, version, palette. Everything derives from here |
| `image/Containerfile` | The operating system |
| `image/overlay/` | Files baked into the root filesystem |
| `image/config.toml.in` | Disk-image settings, templated with your ssh key |
| `webapps/apps.d/` | One file per streaming service |
| `webapps/freetvos-webapp` | The shared launcher every service runs through |
| `cast/dial/` | DIAL receiver, for phone-initiated launches |
| `tools/` | Build, disk, run, screenshot |
| `docs/ASSETS.md` | What artwork is needed, at what sizes |
| `docs/asset-showcase.html` | Every brand asset, shown where it appears on the television |
| `docs/BRANDING.md` | Every Fedora and KDE mark between power-on and the home screen |
| `docs/REMOTE.md` | Using a phone as the remote |
| `docs/EXTENSIONS.md` | Browser extensions, and the truth about "force 1080p" |
| `docs/MULTIVIEW.md` | Split-view design, costs and where it stopped |
| `docs/HDMI-INPUT.md` | Watching a console through a USB capture device |
| `docs/SERVICES.md` | Adding and removing apps on the device |
| `docs/LIBRARY.md` | Your own media, from a drive or a server |
| `docs/EXTRAS.md` | Picture, sound, Bluetooth and game streaming |
| `docs/SCORES.md` | Live scores, and the ESPN feed behind them |
| `docs/SETUP.md` | The first-run wizard, and typing on a television |
| `docs/TICKERS.md` | Stock, score and custom bars along the bottom of the screen |
| `docs/LIVETV.md` | Channels and a guide from Tunarr, a tuner or a playlist |
| `docs/PIP.md` | One service full screen and another small in a corner |
| `docs/MEETINGS.md` | Zoom, Meet and Teams calls, and what is verified about the camera |
| `docs/RESOURCES.md` | How much memory and CPU it uses, and how much RAM a box needs |
| `docs/INSTALL.md` | Getting it onto real x86_64 hardware |

## First run

The first time it is turned on it opens a wizard: join a network, then pick the
apps you use. Both are skippable and **Setup** on the home screen runs it again.
See `docs/SETUP.md`.

## Adding an app

**Apps** on the home screen opens a catalogue of twenty services; Enter adds one
and Enter again removes it. Anything else goes in by name and web address. A
service added this way lives entirely in the user's own directories, so it needs
no rebuild and survives updates. See `docs/SERVICES.md`.

## Curating the home screen

The grid is built from installed desktop entries, so packages put their own
applications on your television. `/etc/freetvos/apps.conf` lists what to hide,
and the build applies it, so a fresh image comes up already curated rather than
needing a first-run cleanup.

At runtime, `freetvos-apps list` shows every entry and its state. Changing the
list means a rebuild: hiding is done by setting NoDisplay in the shipped entry,
which is the only mechanism that reliably reaches Bigscreen's model.

## Pinning a show

A pin is a deep link into a service that already has a tile, with real artwork.
It runs through that service's own wrapper, so it shares the profile, the user
agent and the Widevine wiring rather than becoming a half-configured copy.

**From the remote**, press the **favourites** key while the show is on screen,
or **P** on a keyboard or the KDE Connect phone keyboard. A panel shows its name
and poster: Enter pins it, and it is on the home screen at the end of
Applications. On something already pinned, the same key offers to remove it.
Which remotes' favourites keys reach it is in `docs/REMOTE.md`.

The page's own name and poster are used, which on a service you are signed in to
is better than anything looked up from outside. What the page cannot choose is
where the pin goes: the address comes from the browser, and the service from the
browser window it is running in.

From a terminal:

```bash
freetvos-pin add --name "Stranger Things" --app netflix \
  --url "https://www.netflix.com/title/80057281"
```

Artwork comes from TMDB when a free key is set in `/etc/freetvos/tmdb.conf`,
and otherwise from the linked page's own preview image. Set the key: scraping
is a fallback, not a plan. Netflix serves a generic gate page with no image
metadata unless the request carries a session, so what you get depends on which
page it felt like returning.

What a pin cannot do is show real "continue watching" progress. Netflix,
Disney+ and Hulu publish no API and the resume position lives inside the
service, so the deep link lands on the title's own page where their own Resume
button is. Plex and Jellyfin do publish APIs and could drive a genuine progress
row; that is a separate feature and is not built.

## Adding a service

Write one file. No code changes.

```bash
cat > webapps/apps.d/max.app <<'EOF'
NAME="Max"
URL="https://play.max.com/"
ICON="freetvos-max"
DRM="yes"
USER_AGENT=""
SPATIAL_NAV="no"
EOF
```

A desktop entry is generated at build time, and the Bigscreen home screen picks
it up as a tile.

## Two constraints worth knowing before you plan around them

**DRM works, and needs no setup.** Netflix, Prime Video, Disney+, Hulu,
Paramount+, Peacock, ESPN+, YouTube TV and Apple TV+ all require Widevine, and the module is baked into the image at build time,
so it is there from first boot with no command to run and no network needed.

Set `BUNDLE_WIDEVINE="no"`
in `brand/brand.env` before building anything that leaves the machine; the
device then fetches it itself on first boot, retrying until the network is up,
which is what Raspberry Pi OS and LibreELEC do.

Either way `freetvos-widevine-check` confirms it on screen.

On x86_64 that takes the module straight from Google's own Chrome package. On
ARM there is no such package, because Google publishes no aarch64 Widevine for
desktop Linux at all, so the installer pulls a ChromeOS LaCrOS image from
Google's mirror, extracts the module, and patches it. Two things stop the
ChromeOS binary loading on ordinary glibc, and both are repaired: it uses
DT_RELR relocations without declaring the `GLIBC_ABI_DT_RELR` dependency that
modern glibc demands, and it calls AArch64 outline-atomic helpers that exist in
the ChromeOS toolchain runtime and nowhere else.

Nothing is bundled in the image; the licence does not permit redistribution, so
the module is fetched on the device by its owner. The download is pinned to a
known-good build and checksum-verified.

Confirm it afterwards with `freetvos-widevine-check`, which puts the answer on
the television rather than in a log. Expect it to report L3 and not L1: L1 is
hardware-backed and issued only to licensed device manufacturers, so 1080p and
4K are unreachable on any Linux box. Plex and YouTube need no CDM at all.

Prerequisites the installer checks and will refuse without: glibc 2.35 or newer,
and a 4K-page kernel. The module will not load on the 16K-page kernels used by
Apple Silicon and some ARM server builds.

This is also why every wrapper runs through Chromium rather than the upstream
Bigscreen webapp viewer. That viewer is QtWebEngine, and the aarch64 build only
knows the `_platform_specific/linux_x64` CDM path. It cannot load an ARM
Widevine module at all. Chromium knows `linux_arm64`.

**Chromecast receiving is not possible.** There is no legitimate open Cast
receiver, and there will not be one. What is here instead is DIAL, the open
protocol Cast was built on, which the YouTube and Netflix phone apps still
speak: the phone discovers the TV and tells it which app to open. AirPlay is
genuinely supported through UxPlay, including mirroring.

## Known defects

**The phone and casting features cannot be tested in the VM.** KDE Connect,
AirPlay and DIAL all need the device reachable on the same LAN as the phone.
QEMU's user-mode networking hides the guest behind a NAT, and this QEMU build
has no vmnet backend to bridge with. Everything looks healthy from inside the
guest, which is misleading: the KDE Connect daemon runs and listens on 1716
and is simply undiscoverable. Real hardware is the only way to know.

**The TV settings window is light, and the rest of the system is dark.** It is
the right application now, key-navigable with large type, but it renders in a
light palette no matter what. Its QML reads Kirigami.Theme rather than
hardcoding colours, and the colour scheme, the Plasma theme and the QtQuick
Controls style were all set dark and verified in config; it stays light anyway.
Its own System page has a Global theme picker, which is the remaining thing to
try. Every other Qt dialog on the device is dark.

## Not done yet

- Real hardware. Raspberry Pi 5 needs bootloader work Fedora does not do yet.
- Remote keys for split view. Its shortcuts are on Ctrl+Alt chords no remote
  sends, and Meta is taken by the home overlay.
- The DIAL receiver answers discovery and returns valid app state, but has
  never been driven by a real phone.
- x86_64 disk images cannot be cross-built on Apple Silicon: the builder runs
  podman inside itself and that fails under emulation. The container image
  builds fine, so installation goes through `bootc install` on the target
  instead. See `docs/INSTALL.md`.
- Remote keys for split view. The shortcuts are on Ctrl+Alt chords that no
  remote sends, and Meta is taken by the home overlay.
- Real continue-watching from Plex and Jellyfin, which unlike the DRM services
  do publish the necessary APIs.
