#!/usr/bin/env bash
# Install Widevine on the development VM, using a host-side cache.
#
# The CDM lives in /var, which bootc-image-builder recreates on every disk
# build, so it disappears each time the image is rebuilt. On real hardware this
# is a one-time step that survives updates; in the development loop it is not,
# and re-downloading the image every time is a hundred megabytes of nothing.
set -euo pipefail
cd "$(dirname "$0")/.."
# shellcheck disable=SC1091
. brand/brand.env

CACHE_DIR="${CACHE_DIR:-output/cache}"
LACROS_NAME="chromeos-lacros-arm64-squash-zstd"
LACROS_VERSION="120.0.6098.0"
LACROS_SHA256="38a57cc3975af68675a1219b00354f08890ff58d0c54b690dcf5d2dd904b1576"
CACHED="$CACHE_DIR/$LACROS_NAME-$LACROS_VERSION"

mkdir -p "$CACHE_DIR"
if [ ! -f "$CACHED" ]; then
  echo ">> Caching the LaCrOS image on the host (once)"
  curl -fL --progress-bar -o "$CACHED.part" \
    "https://commondatastorage.googleapis.com/chromeos-localmirror/distfiles/$LACROS_NAME-$LACROS_VERSION"
  mv "$CACHED.part" "$CACHED"
fi

ACTUAL="$(shasum -a 256 "$CACHED" | cut -d' ' -f1)"
[ "$ACTUAL" = "$LACROS_SHA256" ] || {
  echo "!! Cached image checksum mismatch; delete $CACHED and retry" >&2
  exit 1
}
echo ">> Cache verified"

echo ">> Copying to the VM"
scp -P 2222 -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
  -o LogLevel=ERROR "$CACHED" root@localhost:/var/tmp/lacros.squashfs

echo ">> Installing"
ssh -n -p 2222 -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
  -o LogLevel=ERROR root@localhost \
  "LACROS_FILE=/var/tmp/lacros.squashfs /usr/bin/freetvos-widevine-install"
