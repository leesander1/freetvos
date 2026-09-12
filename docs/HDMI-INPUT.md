# External inputs: a console or set-top box on the television

A television without inputs is not really a television. This box has outputs
only, so an input is added the way people actually do it: a USB HDMI capture
device, the ten-dollar kind, which the kernel already recognises as an ordinary
video-capture device. No drivers are involved.

Plug the dongle into the box, plug the console into the dongle, and **Inputs**
appears on the home screen. Selecting it lists what is connected. Back returns
to where you were, from the input or from the list.

## What it does

**Finds the device and decides what to ask it for.** A dongle advertises every
combination it can name, which on the common MacroSilicon parts means 1080p
compressed at thirty frames and 1080p raw at five. Both are "1080p"; only one is
watchable. The rule is largest picture that fits the cap, then highest rate,
then the encoding that reaches the screen soonest. The cap is why a dongle that
claims 4K and cannot sustain it still gives a smooth picture.

**Pairs the sound with the picture.** They arrive on two separate USB
interfaces, so the sound is not in the video stream and the player cannot reach
it. It is matched by USB topology rather than by name, because two identical
dongles report identical names and matching those would cross them over. The
sound is then bridged to the speakers, started when a picture appears and torn
down when it goes, so an input nobody is watching is not quietly audible.

**Waits, rather than failing.** A console is usually asleep when you press the
input button. The player is started once, idle, with its window already on
screen, and told to open the device over its own control socket; if there is no
signal it holds a black screen with a message on it and keeps trying behind
that. When the console wakes, the picture appears. Restarting the player every
two seconds instead would drop back to the home screen and away again in a loop
that looks like a crash.

**Switches by itself when you plug something in**, which is the setting's
default and what a television does.

**Tiles alongside the apps.** The input is a window like any other, so the split
view puts a game on one side and a stream on the other, with the sound following
whichever pane has focus. Open the input, open a service, then press the split
shortcut. It is not offered inside the split view picker, which is built from
the web-app definitions and has nothing to say about hardware.

## Settings

The Settings tile inside Inputs. Everything is navigable with a d-pad; nothing
needs a keyboard, which is why names are chosen from a list rather than typed.

| Setting | What it decides |
|---|---|
| Use this device | Whether it is offered as an input at all. A webcam is detected as a camera and ignored by default; anything can be promoted or demoted here |
| Name | What the tile says. HDMI 1, PlayStation, Cable box and so on |
| Picture | The size and rate to ask for, or automatic |
| Sound | Which capture device the sound comes from, or none |
| Shape | Leave the aspect alone, force 16:9 or 4:3, fill the screen, or zoom |
| Smooth interlaced video | For a source sending 1080i |
| When it is plugged in | Per device, overriding the setting below |
| When a device is plugged in | Switch to it, or do nothing |
| Hold sound back | Delay the sound to land with the picture. Lower for games |
| Largest picture to ask for | The cap described above |
| Skip the list with one input | Go straight to the picture when only one thing is connected |

Defaults live in `/etc/freetvos/hdmi.conf`. Your own choices are written to
`~/.config/freetvos/hdmi.conf` and `~/.config/freetvos/hdmi.d/`, keyed by how
each device identifies itself, so settings follow the device rather than the
socket it happens to be in. Both files are the same shell-style format as the
rest of the system and are safe to edit by hand.

There is deliberately no "just tell me" option for a newly connected device.
Bigscreen's shell never claims the notification bus name, and the file that
would let D-Bus start a service to claim it is misnamed in Fedora's packaging,
so a corner message is accepted by the system and then drawn by nobody.
Offering that setting would be offering something that silently does nothing.

## From a terminal

```bash
freetvos-hdmi list        # what is connected, and what it will be opened as
freetvos-hdmi status      # settings, and whether the tools it needs are here
freetvos-hdmi open HDMI\ 1
freetvos-hdmi selftest    # a test pattern through the same path, no dongle
```

`selftest` is worth knowing about on real hardware: if the pattern is smooth and
Back returns you to the home screen, anything still wrong is the dongle or the
cable rather than this.

## Buying one

Anything the kernel sees as a UVC capture device works. The parts these have
been written around are MacroSilicon's MS2109 and MS2130, which is most of what
is sold cheaply. Two things to check:

- **USB 3 matters more than the price.** A USB 2 dongle cannot carry 1080p raw
  faster than a few frames a second, so it compresses instead, and compression
  is where the delay comes from.
- **Latency is real and is not fixable here.** Capture adds somewhere between a
  twentieth and a fifth of a second. That is fine for watching and noticeable
  when playing. Nothing in this software can remove it; it happens inside the
  dongle before the picture arrives.

## What has been tested, and what has not

Tested in the VM against the kernel's own virtual capture driver, which
advertises formats and streams frames exactly as a real device does: detection,
format choice, the source list, the settings page driven by remote keys, saving
and reloading, automatic switching on connect, waiting through a missing signal
and recovering when it returns, exiting back to the home screen, and tiling
against a streaming service.

Not tested, because it needs the hardware: a real dongle's own quirks, the
sound path end to end, hardware-accelerated decoding of the capture stream, and
the actual latency. The sound bridge and the audio-follow in split view are
written and unexercised, since the virtual driver produces no sound.
