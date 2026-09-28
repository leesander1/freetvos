# Updates

A FreeTVOS television updates itself. Each new version downloads in the
background, and the television restarts to finish it in the middle of the
night, never while something is playing. Settings, wifi, streaming logins,
tickers and pinned shows all stay as they were.

**Updates** on the home screen has the switch, and shows which version is
running and whether a new one is waiting.

## The Updates page

| Row | What it does |
|---|---|
| Update automatically | **On**, the default, or **Off**. Off stops the nightly check and the restart; nothing downloads unless you ask |
| This version | When the running version was built |
| The line under it | Up to date, an update ready, checking, or why the last check failed |
| Check for an update now | Asks straight away and downloads anything new. It never restarts; that works with automatic updates off too |
| Restart now to finish the update | Shown only when an update is waiting |

Closing the page does not stop a check or a download already under way.

## When it happens

- **Every night**, at a random time between 2:15 and 3:00, the television looks
  for a new version and downloads it.
- **Then it restarts to finish**, but only between 2:00 and 5:30, and only once
  nothing is playing. If something is, it looks again every ten minutes. If
  morning comes first, the update waits.
- **Twenty minutes after every start** it also checks. That is for a television
  switched off at the wall overnight: it downloads during the day, and never
  restarts in the daytime.

An update that is waiting finishes the next time the television restarts for
any reason, whether that is the next night, the Restart row, or the power
button.

"Playing" means a stream that is actually making sound. Something paused, the
home screen, or a silent menu does not count.

## Where updates come from

The whole system is one container image. The GitHub build
(`.github/workflows/installer.yml`) publishes it to GitHub's container
registry every time it builds an installer, as
`ghcr.io/<owner>/<repo>:latest`, and also tagged with the commit, for example
`:fc1b0c4`. **Every push to main that changes the image is an update for every
television following it.**

The published image leaves Widevine out, as the installer does. The television
fetches Widevine itself and keeps it in `/var`, which updates never touch.

The package must be **public** for televisions to download it without logging
in. GitHub makes a new package private. Change it once under the repository's
Packages, then Package settings, then Change visibility.

## Which televisions follow it

An installer built by that workflow points the television at the published
image during the install, so it is set up from the first boot.

A television installed some other way follows whatever it was installed from,
often a copy that cannot be downloaded again. The Updates page then says it is
"not set up to receive updates yet". Point it at the published image once, over
ssh:

```bash
sudo bootc switch ghcr.io/leesander1/freetvos:latest
```

That downloads the current version and finishes on the next restart. From then
on it updates like any other.

The first nightly check after an install may download the whole system once,
a few gigabytes, even though nothing changed. The copy on the USB stick and the
published copy are the same system, but they are packed differently, so they
do not look the same to the download.

## Going back

bootc keeps the previous version beside the current one. If an update is bad:

```bash
sudo bootc rollback
sudo systemctl reboot
```

The previous version is also in the boot menu. To stay on one particular
version, switch to its commit tag and turn automatic updates off:

```bash
sudo bootc switch ghcr.io/leesander1/freetvos:fc1b0c4
freetvos-update off
```

`sudo bootc switch ghcr.io/leesander1/freetvos:latest` and `freetvos-update on`
return to following the newest.

## From a terminal

```bash
freetvos-update status          # the version, and whether one is waiting
freetvos-update off             # or on
sudo freetvos-update check      # check and download now, never restart
sudo bootc status               # bootc's own view, in full
journalctl -u freetvos-update   # what the nightly run did
```

## How it is built

bootc's own timer, `bootc-fetch-apply-updates.timer`, downloads an update and
restarts the machine the moment it has one, whatever is on screen. The image
masks it. In its place:

| Unit | Does |
|---|---|
| `freetvos-update.timer` | Starts `freetvos-update auto` every night and 20 minutes after each start |
| `freetvos-update-check.path` | Starts `freetvos-update check` when the page leaves `~/.config/freetvos/update-request` |
| `freetvos-update-status.service` | At each start, writes down which version is running |

The switch is kept in the television account's own
`~/.config/freetvos/updates.json`, so the page changes it without a password.
Only root may ask bootc anything, so the root side writes what the page shows
to `/var/lib/freetvos/update-status.json`, which anyone can read.
