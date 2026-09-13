NAME="Jellyfin"
# There is no Jellyfin website: the web client is served by your own server.
# freetvos-jellyfin opens the server Library is signed into, or Library's own
# sign-in page when there is none. This address is only the fallback for a
# launch that bypasses it, which is a server on the television itself.
URL="http://localhost:8096/web/"
ICON="freetvos-jellyfin"
CATEGORY="AudioVideo;Video;Player;"
# Your own files, unencrypted.
DRM="no"
LAUNCHER="/usr/bin/freetvos-jellyfin"
SPATIAL_NAV="yes"
