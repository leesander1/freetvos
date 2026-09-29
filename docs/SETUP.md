# First-run setup

The television used to boot to a grid with no network joined and nobody signed
in, and the only way to join a wifi network was Plasma's own dialogs, which
assume a mouse. Now it opens a wizard the first time it is turned on.

Two steps and a way out of each:

1. **Network.** A cable is detected and says so. Otherwise the networks in range
   are listed strongest first, with the password typed on screen.
2. **Apps.** The catalogue of nineteen more services, ticked on and off, and
   Moonlight, which is a download rather than a tile.
   Netflix, Prime Video, Disney+, Hulu, Apple TV+, Paramount+, Peacock, ESPN+,
   YouTube, YouTube TV, Plex and Jellyfin are already there.

Nothing is compulsory. **Skip for now** goes straight to watching, and **Setup**
on the home screen runs it again whenever you want.

## The time zone sets itself

There is no time zone question. The clock is kept right by chrony, and each
time a network connection comes up the television asks Fedora's geoip service,
the one Fedora's own installer uses to guess a time zone, where the connection
is, and sets the zone from the answer (`freetvos-timezone`, run by a
NetworkManager dispatcher script). The request goes to
`geoip.fedoraproject.org` and says nothing but the connection's address.

To choose one by hand, which also stops the lookup:

```bash
sudo freetvos-timezone set America/Chicago
sudo freetvos-timezone automatic      # back to following the connection
freetvos-timezone status
```

## It only ever asks once

Finishing writes a stamp to `~/.local/state/freetvos/setup-done`, and so does
walking away from it. A wizard that returns on every boot until it is completed
is a wizard nobody can get past, and there is no support line to ring.

`freetvos-setup reset` lets it run again. The unit behind it is
`freetvos-setup.service`, started as soon as the shell is, so the wizard is the
first thing on screen. It used to wait twelve seconds, which showed the home
screen first; a window opened that early was landing behind the shell because
of KWin's focus stealing prevention, and the FreeTVOS KWin script now makes
every newly opened window the active one.

## The keyboard is the page's own

Plasma ships an on-screen keyboard. It is installed, it runs, the compositor
reports over its own interface that it is `available` and that the focused
browser window `activeClientSupportsTextInput`, and calling `forceActivate`
flips `active` to true. It never draws itself. That was worth chasing down,
because a television whose wifi password cannot be typed is not set up at all.

So the pages draw their own: a grid of characters walked with the arrow keys,
which is what televisions did before any of this existed and which cannot fail
to appear. It is in the shared page module, so every text field on this system
uses it. A keyboard plugged into the box still types straight through.

Once you type on a real keyboard, **Enter means Done**, as in any text box. It
used to press whichever on-screen key was highlighted, which added a stray
character to the end of a typed wifi password. Pressing an arrow key hands Enter
back to the on-screen keys, so a remote works the same as always.

## What has been tested

Everything except a radio. The wizard opening by itself on a fresh boot, the
wired case, the app step adding a service, finishing, the stamp, and the wizard
staying away afterwards are all verified on the device. The wifi half is
verified against recorded `nmcli` output: the terse format with escaped colons
in network names, one entry per network rather than one per access point, open
networks, hidden ones, the sort order, and the difference between a refused
password and a network that stopped answering.

What is not verified is any of that against a real card. `mac80211_hwsim`, the
kernel's virtual radio, is not in this image and a VM has no other, so there is
nothing here to scan. Adding a hundred megabytes of kernel modules to every
television to test one screen was not the trade to make.

## From a terminal

```bash
freetvos-setup status
freetvos-setup networks
freetvos-setup run
freetvos-setup reset
```
