# Terminal

**Terminal** on the home screen opens Konsole, KDE's terminal, full screen in
the FreeTVOS colours and in type that reads from across a room, with no
toolbars or scrollbar: those are for a pointer. Shift+Page Up scrolls back. It needs a
keyboard: a USB or Bluetooth one, or the on-screen keyboard at a push. `exit`
closes it.

It runs as the television's own account, `tv`, which may use `sudo` with no
password, so the fixes this project has needed are one line each:

```bash
sudo bootc upgrade && sudo systemctl reboot     # take an update now
sudo freetvos-widevine-install                  # fetch Widevine again
sudo freetvos-timezone set Europe/London        # choose a time zone
journalctl -b -u freetvos-update                # what the updater did
freetvos-update status
```

## Letting someone in over ssh

The account has no password, so ssh needs a key. From the Terminal, one line
adds the public keys of a GitHub account:

```bash
mkdir -p ~/.ssh && curl -fsSL https://github.com/USERNAME.keys >> ~/.ssh/authorized_keys
```

After that, `ssh tv@<the television's address>` works from a machine holding
that key, and `sudo` works there too. Remove the line from
`~/.ssh/authorized_keys` to take the access away.

## The cost of sudo without a password

Deliberate, and worth stating plainly. The account logs in by itself and has
no password to type, so a password prompt would make `sudo` unusable. The
other side of that: anything that runs as `tv` can become root. That includes
someone at the television with a keyboard, anyone whose ssh key you add, and a
flaw in anything that runs as `tv`, such as the DIAL casting receiver, which
answers on the local network.

The rule is one file, `/etc/sudoers.d/freetvos`. To build an image without it,
delete the file from `image/overlay/etc/sudoers.d/`. To take it away on one
television, `sudo rm /etc/sudoers.d/freetvos`; an update brings it back unless
the image leaves it out.

## Why a launcher

Konsole keeps whether its toolbars show inside Qt's saved window state, in
`~/.local/state/konsolestaterc`, and restores it every time, so a default of
hidden only ever held for the first start. `freetvos-terminal` writes a state
with both toolbars hidden before starting Konsole each time.
