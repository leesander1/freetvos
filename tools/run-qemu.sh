#!/usr/bin/env bash
# Boot the built image on this Mac.
#
# aarch64 with HVF, so the guest runs at native speed on Apple Silicon rather
# than under emulation. Same architecture as a Raspberry Pi or an ARM TV box,
# which is what makes this a useful proxy for the real target.
set -euo pipefail
cd "$(dirname "$0")/.."
# shellcheck disable=SC1091
. brand/brand.env

DISK="${1:-output/qcow2/disk.qcow2}"
[ -f "$DISK" ] || { echo "no disk at $DISK — run 'make disk' first" >&2; exit 1; }

FW="/opt/homebrew/share/qemu/edk2-aarch64-code.fd"
VARS="output/edk2-vars.fd"
[ -f "$FW" ] || { echo "missing UEFI firmware at $FW (brew install qemu)" >&2; exit 1; }

# UEFI needs writable variable storage of exactly the firmware's size.
if [ ! -f "$VARS" ]; then
  mkdir -p output
  dd if=/dev/zero of="$VARS" bs=1m count=64 2>/dev/null
fi

# RAM=2048 boots with less memory, for finding what the television needs to
# run smoothly. The default is 4 GB.
#
# HEADLESS=1 swaps the window for a serial console, which is how you read the
# boot log and confirm services actually came up. The graphical mode shows the
# shell but tells you nothing when it fails to start.
if [ "${HEADLESS:-0}" = "1" ]; then
  # -display none, not -nographic. -nographic tears down the graphics
  # adapter, so the guest never sets a mode and screendump captures an
  # inactive output. -display none keeps the virtual GPU scanning out to a
  # framebuffer nobody is watching, which is exactly what a screenshot needs.
  DISPLAY_ARGS=( -display none -serial file:output/console.log )
else
  DISPLAY_ARGS=( -display cocoa,show-cursor=on -serial file:output/console.log )
fi

# USB_IMG=output/usb.img attaches a drive to the emulated USB bus, which is the
# only way to exercise the automounter: there is no other source of a hotplugged
# block device in a VM.
#
# Expanded below with the ${a[@]+...} form: the bash macOS ships (3.2) calls an
# empty array unbound under set -u, so a plain "${USB_ARGS[@]}" refused to boot
# whenever no drive was attached.
USB_ARGS=()
if [ -n "${USB_IMG:-}" ]; then
  [ -f "$USB_IMG" ] || { echo "no USB image at $USB_IMG" >&2; exit 1; }
  USB_ARGS=(
    -drive "if=none,id=stick,format=raw,file=$USB_IMG"
    -device usb-storage,drive=stick,removable=on
  )
fi

exec qemu-system-aarch64 \
  -machine virt,accel=hvf,highmem=on \
  -cpu host \
  -smp 4 \
  -m "${RAM:-4096}" \
  -drive "if=pflash,format=raw,readonly=on,file=$FW" \
  -drive "if=pflash,format=raw,file=$VARS" \
  -drive "if=virtio,format=qcow2,file=$DISK" \
  -device virtio-gpu-pci,xres=1920,yres=1080 \
  -device qemu-xhci \
  -device usb-kbd \
  -device usb-tablet \
  ${USB_ARGS[@]+"${USB_ARGS[@]}"} \
  -audiodev coreaudio,id=snd0 \
  -device intel-hda -device hda-duplex,audiodev=snd0 \
  -nic user,model=virtio-net-pci,hostfwd=tcp::2222-:22 \
  "${DISPLAY_ARGS[@]}" \
  -qmp "unix:output/qmp.sock,server=on,wait=off" \
  -name "$BRAND_NAME"
