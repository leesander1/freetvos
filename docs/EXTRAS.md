# Picture, sound, Bluetooth and game streaming

## Picture & Sound

A tile of its own, because Plasma's television settings application will not
start from anything but the shell itself and shows nothing when it does not.

| Setting | What it does |
|---|---|
| Size and rate | Every mode the screen reports, largest and smoothest first |
| Pull the picture in from the edges | Overscan, for a television that crops |
| Output | Where sound goes: the television, headphones, a USB device |
| Volume, Silence | The system volume, not one application's |
| Headphones and remotes | Pair, connect and disconnect Bluetooth devices |

Picture and output changes apply on Enter rather than while cycling. Stepping
through screen modes and applying each one on the way past would black the
television out several times.

Changing the output also moves whatever is already playing. Setting the default
alone moves nothing that has already started, so a film carries on coming out of
the television while the headphones sit silent, which reads as the setting having
done nothing at all.

The Bluetooth half asks the kernel whether an adapter exists before asking
bluez anything. `bluetoothctl` does not answer that question quickly: with no
adapter it waits for one to appear until something kills it, and a page that
asks before drawing then never draws. That was a real fault, found by the page
coming up blank.

### Not covered

Networking and everything else stays in the Settings tile, which is Plasma's own
and is the one the shell's settings button opens. Two settings applications is
one too many, but replacing that one would leave the shell button and the tile
going to different places, which was already reported once as confusing.

## Game streaming

**Game Streaming** runs Moonlight, which plays a game running on a PC elsewhere
in the house. It is not packaged for Fedora, so it arrives as a Flatpak,
installed into the viewer's own directory: that needs no root, and under bootc it
is the only place it could persist, since `/usr` is a read-only image.

Nothing is installed until somebody asks. The application is eight megabytes and
the runtime underneath it is most of two gigabytes, and a television that spends
its first boot quietly downloading that is a television that appears broken. The
tile explains the size, and the page reports progress while it works.

Moonlight wants hardware video decoding and says so loudly if it cannot find
any. In a VM it cannot; on real hardware with working VAAPI it will.

```bash
freetvos-moonlight status
freetvos-moonlight install
freetvos-moonlight remove
```
