NAME="Plex"
URL="https://app.plex.tv/desktop"
ICON="freetvos-plex"
CATEGORY="AudioVideo;Video;Player;"
# Personal media is unencrypted, so no CDM is needed for the common case.
# Plex-distributed movies and live TV do use Widevine and will fail without it.
DRM="no"
# Plex ships a genuine TV layout and handles arrow keys itself.
SPATIAL_NAV="yes"
