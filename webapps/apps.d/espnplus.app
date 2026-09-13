NAME="ESPN+"
URL="https://plus.espn.com/"
ICON="freetvos-espnplus"
CATEGORY="AudioVideo;Video;Player;TV;"
DRM="yes"
# Live events are the part that matters here, and they are Widevine protected
# like everything else. ESPN folded ESPN+ into its own app in 2025; this address
# still lands on the ESPN+ side, and a local definition can move it without a
# rebuild if that stops being true.
USER_AGENT="Mozilla/5.0 (X11; CrOS aarch64 15236.80.0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
SPATIAL_NAV="yes"
