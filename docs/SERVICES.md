# Adding services without rebuilding

The twelve services in the image are definitions in `/usr`, turned into tiles at
build time. That is right for what the product ships with and wrong for
everything else: wanting Spotify on your own television should not mean building
an operating system.

**Apps** on the home screen opens a catalogue of nineteen more services. Enter adds one,
Enter again removes it. There is nothing to type, because typing with a d-pad is
miserable and most people want one of the same few.

For anything else there is **Add by web address**, which takes a name and an
address and makes a tile out of it. Your own Jellyfin, a webmail client, a
camera's web interface, anything that plays in a browser.

## Where things go

| What | Where |
|---|---|
| The definition | `~/.config/freetvos/webapps/<id>.app` |
| The tile | `~/.local/share/applications/freetvos-<id>.desktop` |
| The icon | `~/.local/share/icons/hicolor/<size>/apps/freetvos-<id>.<ext>` |
| The service's cookies and logins | `~/.local/share/freetvos/webapps/<id>/` |

Nothing is written to `/usr`, which under bootc is a read-only image: anything
that did land there would fail outright and be discarded by the next update.

The launcher reads the local directory before the image's, so a definition added
here also overrides a shipped service of the same name. That is the only way to
follow a provider who moves their address without rebuilding the whole system.

Removing a service leaves its profile alone, so a login comes back if you add it
again.

## Icons

Taken from the service's own site rather than drawn here. Twenty hand-drawn
logos would be twenty pieces of someone else's branding to keep current, and
would do nothing for a service you add by address, which is the point.

The rules, in order:

- A logo drawn for this product wins. Two exist, for Spotify and Apple Music,
  because both sites offer nothing above browser-tab size.
- Otherwise the site's own declared icons, largest first, measured from the file
  rather than trusted from its `sizes` attribute, which is often wrong.
- A black-on-transparent favicon is put on a light plate. Left alone it is
  very nearly invisible on a dark tile.
- Failing all of that, the service's initial on a plain tile.

Windows `.ico` files are skipped. They are usually sixteen or thirty-two pixels,
which on a television is a smudge, and decoding one would mean a raster library
the image does not otherwise need.

## From a terminal

```bash
freetvos-service catalogue
freetvos-service add spotify
freetvos-service add --name "My Jellyfin" --url jellyfin.local:8096
freetvos-service remove spotify
freetvos-service list
```

`--drm` marks a service as needing Widevine, which makes the launcher refuse
early with a useful message rather than opening a black player.

## Jellyfin

Jellyfin is built in, but it is not a website the way Netflix is. Its web client
is served by whoever runs the server, so the tile cannot carry a fixed address.
It opens the server **Library** is signed into. With none yet, it opens Library's
page asking where the server is, so the tile is never a dead end.

The web client keeps its own sign-in, separate from Library's, and asks once the
first time it opens. Quick Connect works there too.

## Typing on a television

Every text field here types through a keyboard the page draws itself: a grid of
characters walked with the arrow keys. A keyboard plugged into the box still
types straight through.

Plasma's own on-screen keyboard is not used, because it does not work on this
shell. It is installed and running, and the compositor reports it as available
and active over a text field, and it never draws. Adding by address and the
Jellyfin server address both relied on it until that was found, which meant
neither could be filled in from a remote at all.
