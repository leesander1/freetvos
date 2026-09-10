NAME="Netflix"
URL="https://www.netflix.com/browse"
ICON="freetvos-netflix"
CATEGORY="AudioVideo;Video;Player;"
DRM="yes"
# Left as the honest Linux UA on purpose. Netflix serves Linux Chrome without
# complaint, and spoofing a Windows UA asks for a robustness level the
# sideloaded L3 module cannot supply, which fails harder than it helps.
# Expect 720p. HD on Netflix needs hardware-backed L1, which no Linux box has.
USER_AGENT=""
SPATIAL_NAV="no"
