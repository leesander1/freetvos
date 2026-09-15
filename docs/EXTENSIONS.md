# Browser extensions

Every service tile runs through Chromium, so extensions work. Drop an unpacked
extension into a directory and every web app picks it up on next launch:

```
~/.local/share/freetvos/extensions/<name>/manifest.json
```

Each subdirectory holding a `manifest.json` is loaded. Set `EXTENSIONS="no"` in
a service's `.app` file to launch that one clean, which is the first thing to
do when diagnosing a playback problem.

One caveat worth re-checking after a Chromium update. Google disabled
`--load-extension` upstream in Chrome 137 on security grounds. Fedora's
Chromium 152 build still honours it, verified by loading a probe extension and
watching it run, but that is a thing that could change under you.

## The two that ship

`tv-focus` draws a focus ring a television can see, and a border around the pane
in focus in split view.

`tv-pin` is the pin key: the favourites key on a remote, or P, opens a panel that
pins the show on screen to the home screen. It is the only extension here with a permission,
`nativeMessaging`, which lets it start one program:
`/usr/bin/freetvos-pin-host`, registered in
`/etc/chromium/native-messaging-hosts/org.freetvos.pin.json`. The registration
names the extension by ID, and the ID is fixed by the public key in its manifest,
so no other extension can start the helper.

## On the "force 1080p" extensions

The honest position, because the internet is confident about this and the
picture is more mixed than it looks.

**What they actually do.** The Netflix 1080p family intercepts the manifest
request and asks for higher video profiles than the player requests by default.
They do not touch the CDM, break encryption, or alter the licence exchange.
Netflix's servers still decide what to send.

**Why they existed.** On Chrome for Windows, Netflix's 720p ceiling was partly
a profile-list policy rather than a hard DRM decision, so asking for the better
profiles sometimes got them. That is the environment these extensions were
written and tested for.

**Why it may not carry over here.** This device runs an L3 CDM extracted from a
ChromeOS build, on ARM, on Linux. If Netflix's licence server declines to issue
keys for the 1080p tracks at that robustness level, the request simply fails
and the player falls back or errors. Whether it does is an empirical question
about someone's account, and it has not been tested here: that needs real
credentials, which this project does not have and should not ask for.

So: it may work, it may do nothing. Install one and see. It costs a directory.

**What cannot work, whatever a forum says.** Anything claiming to turn L3 into
L1 by patching the CDM or spoofing the reported security level. The level is
carried in the licence request inside a client identification blob signed with
keys provisioned into the device at manufacture. A device without L1 keys
cannot produce a signature for L1, so the server rejects it. This is not a
matter of finding the right flag; it is the part of the system that is actually
cryptography rather than policy.

**Terms of use.** Netflix's terms prohibit circumventing their content
protections. Whether a manifest-rewriting extension crosses that line is a
judgement for the account holder, not for this document.

## Where the resolution win actually came from

Worth knowing before reaching for an extension. The real defect was that
Chromium picked up a Wayland output scale and reported a 945x1060 viewport on a
1920x1080 panel. Services choose quality from player size, so that alone held
YouTube below 1080p. Passing an explicit window size fixed it, and that applies
to every service, DRM or not, with no extension involved.
