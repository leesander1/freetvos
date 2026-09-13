# First-run setup

The television used to boot to a grid with no network joined and nobody signed
in, and the only way to join a wifi network was Plasma's own dialogs, which
assume a mouse. Now it opens a wizard the first time it is turned on.

Two steps and a way out of each:

1. **Network.** A cable is detected and says so. Otherwise the networks in range
   are listed strongest first, with the password typed on screen.
2. **Apps.** The catalogue of twenty services, ticked on and off. Netflix,
   Disney+, Hulu, Apple TV+, YouTube, YouTube TV and Plex are already there.

Nothing is compulsory. **Skip for now** goes straight to watching, and **Setup**
on the home screen runs it again whenever you want.

## It only ever asks once

Finishing writes a stamp to `~/.local/state/freetvos/setup-done`, and so does
walking away from it. A wizard that returns on every boot until it is completed
is a wizard nobody can get past, and there is no support line to ring.

`freetvos-setup reset` lets it run again. The unit behind it is
`freetvos-setup.service`, started twelve seconds into the session, because a
window that maps into a session still starting up lands behind the shell.

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
