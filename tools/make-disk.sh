#!/usr/bin/env bash
# Turn the container image into a bootable disk image.
#
# bootc-image-builder runs privileged and reads the host's container storage
# directly, which is why it needs both the socket-level access and the storage
# bind mount. Output lands in ./output.
set -euo pipefail
cd "$(dirname "$0")/.."
# shellcheck disable=SC1091
. brand/brand.env

ARCH="${1:-$ARCH_DEFAULT}"
TYPE="${2:-qcow2}"   # qcow2 | raw | anaconda-iso
case "$ARCH" in
  arm64|aarch64) ARCH=arm64 ;;
  amd64|x86_64)  ARCH=amd64 ;;
  *) echo "unknown arch: $ARCH" >&2; exit 2 ;;
esac

TAG="${IMAGE_REF}:${BRAND_VERSION}-${ARCH}"
mkdir -p output

# Fill the config template with this developer's public key so the built image
# is reachable over ssh without committing anyone's key to the repository.
SSH_KEY_FILE="${SSH_KEY_FILE:-$HOME/.ssh/id_ed25519.pub}"
if [ -r "$SSH_KEY_FILE" ]; then
  # Collapse to a single line. A .pub file with its comment wrapped onto a
  # second line is valid on disk but breaks both sed and authorized_keys.
  SSH_KEY="$(tr '\n' ' ' < "$SSH_KEY_FILE" | tr -s ' ' | sed 's/ *$//')"
else
  echo "!! No public key at $SSH_KEY_FILE; the image will have no ssh access." >&2
  SSH_KEY=""
fi
sed "s|@SSH_KEY@|${SSH_KEY}|" image/config.toml.in > output/config.toml

echo ">> Producing $TYPE for $ARCH from $TAG"
# --platform matters: the builder installs the target's own packages into the
# image it is assembling, so an aarch64 builder handed x86_64 rpms fails with
# "intended for a different architecture". The builder has to be the same
# architecture as what it is building.
podman run --rm --privileged --platform "linux/${ARCH}" \
  --security-opt label=type:unconfined_t \
  -v "$(pwd)/output:/output" \
  -v "$(pwd)/output/config.toml:/config.toml:ro" \
  -v /var/lib/containers/storage:/var/lib/containers/storage \
  quay.io/centos-bootc/bootc-image-builder:latest \
    --type "$TYPE" \
    --local \
    --target-arch "$ARCH" \
    "$TAG"

echo ">> Output in ./output"
find output -type f -name "*.${TYPE##*-}" -o -type f -name "*.qcow2" -o -type f -name "*.raw" | head
