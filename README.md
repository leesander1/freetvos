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

**DRM caps you at 720p, and on ARM it needs manual setup.** Netflix, Disney+,
Hulu, YouTube TV and Apple TV+ all require Widevine. Linux only ever gets L3,
the software tier, so HD and 4K are unreachable no matter what this project
does; L1 is hardware-backed and issued only to licensed device manufacturers.
Worse on ARM, Google publishes no aarch64 module at all, so it has to be
extracted from a ChromeOS image and patched. `freetvos-widevine-install`
handles x86_64 directly from Google's own Chrome package and points at the
`pivine` project for ARM. Nothing is bundled, because the licence does not
permit redistribution. Plex and YouTube are unaffected.

This is also why every wrapper runs through Chromium rather than the upstream
Bigscreen webapp viewer. That viewer is QtWebEngine, and the aarch64 build only
knows the `_platform_specific/linux_x64` CDM path. It cannot load an ARM
Widevine module at all. Chromium knows `linux_arm64`.

**Chromecast receiving is not possible.** There is no legitimate open Cast
receiver, and there will not be one. What is here instead is DIAL, the open
protocol Cast was built on, which the YouTube and Netflix phone apps still
speak: the phone discovers the TV and tells it which app to open. AirPlay is
genuinely supported through UxPlay, including mirroring.

## Not done yet

- Artwork. Every tile is a blank placeholder. See `docs/ASSETS.md`.
- Real hardware. Raspberry Pi 5 needs bootloader work Fedora does not do yet.
- `plasma-remotecontrollers` is unpackaged in Fedora, so HDMI-CEC and gamepad
  input need a source build. `libcec` is installed and ready for it.
- The DIAL receiver is written but untested against a real phone.
- x86_64 has never been built. `make build ARCH=amd64` should work.
