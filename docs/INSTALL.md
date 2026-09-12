# Installing on real x86_64 hardware

The container image cross-builds on an Apple Silicon Mac without trouble. A
bootable disk does not, and it is worth recording what was tried so nobody
spends the afternoon again.

Building a bootc disk means *running* the target image's own userspace to lay
it out, and qemu-user emulation cannot do the process and namespace work that
requires. Every route ends in the same place:

| Route | Fails with |
|---|---|
| `bootc-image-builder` as aarch64, `--target-arch amd64` | rpm refuses the x86_64 installer packages as "intended for a different architecture" |
| `bootc-image-builder` as amd64 | its nested podman cannot allocate 2048 semaphores |
| ...with `num_locks=128` | crun cannot re-execute itself via a memory file descriptor |
| ...with `runtime=runc` | runc's nsexec cannot spawn stage-1: invalid argument |
| `bootc install to-disk --via-loopback` | cannot re-exec into the host mount namespace across architectures |

Nor is emulating the result useful. QEMU on Apple Silicon offers only TCG for
x86_64, and no Mac can hardware-accelerate x86 at all, so a Plasma session
would crawl and would answer nothing about performance, which is the main thing
hardware is needed to settle. UTM does not change this; it runs the same
emulation underneath.

A Fedora x86_64 live VM under UTM would work, because inside it everything is
native and the install proceeds normally. It is hours of emulated work for a
result that still runs at emulation speed.

Installing on the machine itself takes minutes and is the shorter path anyway.

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
