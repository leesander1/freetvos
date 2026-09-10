#!/usr/bin/env bash
# Capture what is actually on the TV screen.
#
# Taken through QEMU's own monitor rather than from inside the guest. KWin does
# not implement the wlr-screencopy protocol that grim needs, and the portal
# route wants an interactive permission token, so asking the hypervisor for the
# framebuffer is both simpler and completely invisible to the guest.
set -euo pipefail
cd "$(dirname "$0")/.."

SOCK="output/qmp.sock"
OUT="${1:-output/screenshot.ppm}"
PNG="${OUT%.ppm}.png"
[ -S "$SOCK" ] || { echo "no QMP socket at $SOCK -- is the VM running?" >&2; exit 1; }

python3 tools/qmp-screendump.py "$SOCK" "$(pwd)/$OUT"

# QEMU writes PPM. Convert so the result is viewable in anything.
if command -v sips >/dev/null 2>&1; then
  sips -s format png "$OUT" --out "$PNG" >/dev/null 2>&1 && echo "converted $PNG"
elif command -v magick >/dev/null 2>&1; then
  magick "$OUT" "$PNG" && echo "converted $PNG"
fi
