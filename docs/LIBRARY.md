# Your own media

Three kinds of place, behind one tile.

| Source | How it gets there |
|---|---|
| A USB drive | Plug it in. It mounts itself and appears in the list |
| A Plex server | Sign in by typing a code on your phone |
| A Jellyfin server | The same, using Quick Connect |
| Anything else already mounted | `freetvos-media add-folder /path` |

**Library** on the home screen opens with a continue-watching row, then the
places to look. Everything below that is one page repeated: a grid of things,
some of which you open and some of which you play.

## No password is typed into this television

Both servers publish a linking flow built for devices exactly like this one.
The television asks for a code, shows it on screen, and you enter or approve it
on a device you are already signed into. The password is typed there, into the
service's own page. Nothing in this software ever handles one, which is the only
sensible arrangement for a box sitting in a living room.

The tokens that come back are yours. They live in `~/.config/freetvos/media/`
with permissions that exclude everyone else on the machine, and they are the
only credentials held. `freetvos-media forget plex` throws one away.

## Continue watching

One row, from every source that has an opinion:

- **Plex** contributes its On Deck list, so a programme started on a phone shows
  up here at the right point.
- **Jellyfin** contributes its resume list, the same way.
- **Local files** contribute whatever the player remembered, read out of mpv's
  own watch-later store rather than kept separately. One store means the row and
  the player can never disagree about where something stopped.

A server's position beats the local one when both exist, because the server
knows about every device you own and this one only knows about itself.

## USB drives

Mounted read-only, on purpose. A television reads from a drive and never writes
to it, and somebody will eventually pull the stick out mid-film; a filesystem
that was never mounted for writing cannot be damaged by that.

FAT, exFAT, NTFS and the Linux filesystems all work. Drives without ownership of
their own are given to the appliance user, or nothing could read what had just
been mounted.

## Playing

The remote is laid out the way a television remote is. The middle button plays
and pauses, left and right step ten seconds, up and down jump a minute, and Back
leaves and remembers the position. `s` cycles subtitles, `a` cycles audio tracks,
and `i` says what is playing.

Files are played directly rather than asked for as a transcode. The box is
decoding anyway, and a transcode makes the server work for nothing. Anything the
player cannot decode is a reason to fix the player, not to push the problem up
the wire.

## From a terminal

```bash
freetvos-media sources
freetvos-media resume
freetvos-media link-plex
freetvos-media link-jellyfin jellyfin.local:8096
freetvos-media add-folder /mnt/films --name "The NAS"
freetvos-play /run/media/freetvos/MOVIES/Films/film.mkv
```

## Not built

Mounting a network share. Browsing one is solved, and `add-folder` points the
library at anything already mounted, but mounting SMB or NFS needs credentials
and root, which is a different problem wearing the same clothes. Use `fstab`, or
a Jellyfin or Plex server, which is what most people with a NAS already have.
