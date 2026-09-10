# FreeTVOS

A television operating system built on KDE Plasma Bigscreen, defined as a
bootable container and shipped as an atomically updatable image.

Status: boots to the Bigscreen home screen in QEMU on Apple Silicon, launches
streaming services fullscreen, and receives AirPlay. Not yet ported to real
hardware, and without artwork.

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

**DRM works, but caps at 720p.** Netflix, Disney+, Hulu, YouTube TV and Apple
TV+ all require Widevine, and one command installs it:

```bash
sudo freetvos-widevine-install
```

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

**Desktop applications clutter the tile row.** Chromium, the emoji selector
and other packaged desktop apps appear on the home screen alongside the
streaming services, because Bigscreen builds its grid from every installed
desktop entry. The fix is a set of `NoDisplay=true` overrides in
`/usr/share/applications` for entries that have no business on a television.

**Every tile icon is blank.** The desktop entries already reference the right
names, `freetvos-netflix` and so on, so the artwork only has to be drawn and
installed under `hicolor`. Nothing needs rewiring. See `docs/ASSETS.md`.

**The boot is branded Fedora and KDE, not FreeTVOS.** Five separate surfaces
between power-on and the home screen, catalogued in `docs/BRANDING.md` with the
current value and controlling file for each.

## Not done yet

- Real hardware. Raspberry Pi 5 needs bootloader work Fedora does not do yet.
- `plasma-remotecontrollers` is unpackaged in Fedora, so HDMI-CEC and gamepad
  input need a source build. `libcec` is installed and ready for it.
- The DIAL receiver answers discovery and returns valid app state, but has
  never been driven by a real phone.
- x86_64 has never been built. `make build ARCH=amd64` should work.
