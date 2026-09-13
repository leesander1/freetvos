NAME="Prime Video"
URL="https://www.primevideo.com/"
ICON="freetvos-primevideo"
CATEGORY="AudioVideo;Video;Player;"
DRM="yes"
# The ChromeOS agent, the same as Netflix and for the same reason: an honest
# Chromium on a non-Windows platform is served the L3 path without argument,
# where a spoofed desktop agent is asked for a robustness level this module
# cannot supply. Expect 720p at most, and SD on some titles.
USER_AGENT="Mozilla/5.0 (X11; CrOS aarch64 15236.80.0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
SPATIAL_NAV="yes"
