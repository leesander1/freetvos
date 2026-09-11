#!/usr/bin/env bash
# Build the FreeTVOS container image.
set -euo pipefail
cd "$(dirname "$0")/.."
# shellcheck disable=SC1091
. brand/brand.env

ARCH="${1:-$ARCH_DEFAULT}"
case "$ARCH" in
  arm64|aarch64) ARCH=arm64; BASE_TAG="${FEDORA_RELEASE}-aarch64" ;;
  amd64|x86_64)  ARCH=amd64; BASE_TAG="${FEDORA_RELEASE}-x86_64" ;;
  *) echo "unknown arch: $ARCH" >&2; exit 2 ;;
esac

TAG="${IMAGE_REF}:${BRAND_VERSION}-${ARCH}"
echo ">> Building $TAG from quay.io/fedora/fedora-bootc:${BASE_TAG}"

podman build \
  --platform "linux/${ARCH}" \
  --build-arg "BASE_IMAGE=quay.io/fedora/fedora-bootc:${BASE_TAG}" \
  --build-arg "BRAND_ID=${BRAND_ID}" \
  --build-arg "BRAND_NAME=${BRAND_NAME}" \
  --build-arg "BRAND_VERSION=${BRAND_VERSION}" \
  --build-arg "BUNDLE_WIDEVINE=${BUNDLE_WIDEVINE:-no}" \
  -f image/Containerfile \
  -t "$TAG" \
  .

podman tag "$TAG" "${IMAGE_REF}:latest"
echo ">> Built $TAG"
