# Meetings

Zoom, Google Meet and Microsoft Teams calls on the television, joined with the
remote.

## Joining

**Meetings** asks for what an invitation says: the meeting ID and passcode for
Zoom or Teams, or the code for Meet, typed with the on-screen keyboard. It
builds the address itself and opens the call. A whole invitation link works
too.

| Service | What to type | Opens |
|---|---|---|
| Zoom | Meeting ID, and the passcode if there is one | Zoom's browser client |
| Google Meet | The code, such as `abc-defg-hij` | The meeting in Meet |
| Microsoft Teams | Meeting ID and passcode | Teams' join page for guests |

Typing is forgiving, because invitations are read aloud: spaces in an ID are
ignored, and a Meet code works in capitals or without its hyphens. A pasted Zoom
link, which points at a desktop app this box does not have, is turned into the
browser client's address. A link to anywhere other than these three services is
refused, because the call's browser has the camera switched on.

All three run in the browser because that is the only form any of them offers for
an ARM Linux box. Each call service has its own browser profile, so signing into
one does not sign into anything else, and none of them appears as a tile of its
own: opened with nothing to join, each is only a sign-in page.

## Camera and microphone

A browser asks before a site uses the camera, with a dialog that needs a pointer.
A policy shipped with the image, in `/etc/chromium/policies/managed`, allows the
camera and microphone for these three services only, so a call starts without
the question. Every other site still has to ask.

The page lists the camera and microphone it can see before you join, so a
missing webcam is found here rather than inside the service's own page.

## What has been checked, and what has not

- **The policy is read.** Chromium logs the policy folder as loaded, and a test
  page allowed by the same mechanism was given the microphone with no prompt.
- **Joining.** A Meet code opens Meet in the call's own window. Joining a real
  call needs a real meeting, which was not available.
- **The camera is not verified.** The VM has no webcam. The kernel's virtual
  camera is visible to the system and to PipeWire, but Chromium's own camera
  service lists no devices for it. A USB webcam goes through the same path in
  every Linux Chromium and is expected to work, but nothing here has proved it.

If a USB webcam turns out not to appear either, Chromium can use PipeWire for
cameras instead, which does see them. That route asks through the desktop's own
permission dialog, which is why it is not the default, and it would need the
permission granted ahead of time to stay pointer-free.

## From a terminal

```bash
freetvos-meet devices
freetvos-meet join zoom 812 3456 7890 --passcode 1234
freetvos-meet join meet abc-defg-hij
freetvos-meet join https://us02web.zoom.us/j/81234567890
freetvos-meet join teams 123 456 789 012 --passcode x7Y9 --print
```
