# Installing on real x86_64 hardware

The container image cross-builds on an Apple Silicon Mac without trouble.
Turning it into a bootable disk does not: `bootc-image-builder` runs podman
inside itself, and under emulation that fails with

```
Error: failed to open 2048 locks in /libpod_lock: numerical result out of range
```

for every output type, ISO and raw alike. The disk-assembly step needs a host
of the target architecture.

That is not a problem in practice, because bootc is designed to install from
the container image directly on the target machine, which skips cross-building
entirely and is the shorter path anyway.

## Getting the image onto the machine

Either push it to a registry, or carry it on a USB stick. The stick needs no
account and no network.

```bash
make export ARCH=amd64          # writes output/freetvos-amd64.tar (about 6GB)
```

Copy that file to a USB stick alongside a Fedora Live ISO.

## Installing

Boot the target machine from any Fedora Live USB, then:

```bash
sudo podman load -i /run/media/liveuser/USB/freetvos-amd64.tar
```

Find the disk to install to, and be certain of it, because the next command
erases it:

```bash
lsblk -d -o NAME,SIZE,MODEL
```

Then install. Replace `/dev/nvme0n1` with the disk you just identified:

```bash
sudo podman run --rm --privileged --pid=host \
  --security-opt label=type:unconfined_t \
  -v /dev:/dev -v /var/lib/containers:/var/lib/containers \
  localhost/freetvos:0.1.0-amd64 \
  bootc install to-disk --wipe /dev/nvme0n1
```

Remove the USB stick and reboot.

## What to check first, and why this matters

Three features cannot be tested in the development VM at all, because QEMU's
user-mode networking hides the guest behind a NAT where nothing on the real
network can reach it. This hardware is the first place they can work:

- **KDE Connect.** Pair a phone and check the trackpad and keyboard.
- **AirPlay.** The television should appear as FreeTVOS in the iOS picker.
- **DIAL.** The YouTube phone app should offer to play to it.

Two more that a VM cannot answer honestly:

- **Hardware video decode.** Software decode is fine for a test page and will
  stutter on a real 1080p stream. Check `chrome://gpu` inside a service.
- **The boot splash.** It has never been seen: boot reaches the shell in about
  five seconds and QEMU's display is inactive for part of that window.

## Widevine

Already in the image, baked in at build time, so there is nothing to run. The
first thing worth checking is simply that it survived the trip:

```bash
freetvos-widevine-check
```

Expect L3 and not L1. That is the 720p ceiling and it is the same on every
Linux device, because L1 is hardware-backed and issued only to licensed device
manufacturers.

This only works because the image is not being distributed. If you ever hand
one to someone else, set `BUNDLE_WIDEVINE="no"` in `brand/brand.env` first and
the device will fetch the module itself instead.
