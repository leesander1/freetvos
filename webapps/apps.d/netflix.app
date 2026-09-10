NAME="Netflix"
URL="https://www.netflix.com/browse"
ICON="freetvos-netflix"
CATEGORY="AudioVideo;Video;Player;"
DRM="yes"
# Left as the honest Linux UA on purpose. Netflix serves Linux Chrome without
# complaint, and spoofing a Windows UA asks for a robustness level the
# sideloaded L3 module cannot supply, which fails harder than it helps.
# Expect 720p. HD on Netflix needs hardware-backed L1, which no Linux box has.
USER_AGENT="Mozilla/5.0 (X11; CrOS aarch64 15236.80.0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
SPATIAL_NAV="no"
