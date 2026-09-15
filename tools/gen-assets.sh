#!/usr/bin/env bash
# Generate every FreeTVOS asset from its SVG master. See docs/ASSETS.md and the
# notes at the top of tools/gen-assets.py.
#
#   tools/gen-assets.sh            derived SVGs, every PNG, then a coverage check
#   tools/gen-assets.sh svg        only the derived SVGs
#   tools/gen-assets.sh png        only the PNGs
#   tools/gen-assets.sh check      only the check
#
# The drawing runs in a container holding rsvg-convert and Noto Sans, so nothing
# is installed on this machine and the image build needs no rasteriser.
set -euo pipefail
cd "$(dirname "$0")/.."
IMAGE="localhost/freetvos-assets"
podman build -q -t "$IMAGE" -f tools/assets.Containerfile tools >/dev/null
exec podman run --rm -v "$PWD:/src" -w /src "$IMAGE" python3 tools/gen-assets.py "${1:-all}"
