# Picture in picture

One thing full screen and another small in a corner, on top of it. The big
picture has the remote; the small one is for keeping an eye on.

## Starting it

**Picture in Picture** on the home screen asks for the big picture, then the
small one, using the same picker as split view, and opens both. Anything that is
already open is used rather than opened twice.

From a keyboard, **Ctrl+Alt+P** does the same with whatever is on screen: the
focused window becomes the big picture.

## While it is on

| Key | Command | Does |
|---|---|---|
| Ctrl+Alt+S | `freetvos-split pip-swap` | Swap the big and small pictures |
| Ctrl+Alt+C | `freetvos-split pip-corner` | Move the small picture to the next corner |
| Ctrl+Alt+P | `freetvos-split pip-off` | Back to one picture |

The small picture starts in the top right. The ticker bars sit above every
window along the bottom of the screen, so a small picture in a bottom corner is
placed high enough to clear a stack of them.

Any other layout, such as split view, replaces picture in picture, and closing
either window ends it with the other left full screen.

## Sound

Sound follows the big picture when picture in picture is started from the tile
or the `freetvos-split` commands, including after a swap. Started from the
keyboard shortcut alone, both keep their sound, because the shortcut runs inside
the compositor where the audio is out of reach.

## How it works, and the one thing it has to fight

The layout lives in the same compositor script as split view, because on Wayland
only the compositor may move a window. The big picture is maximised rather than
made fullscreen: the compositor draws a fullscreen window above everything kept
above it, which would bury the small picture.

Some pages put themselves back into fullscreen anyway. YouTube's TV page does it
a moment after being taken out, and the small picture vanished behind it. While
picture in picture is on, the script takes fullscreen straight back off the big
window whenever it returns.

Anything with a window works as either picture: a streaming service, Live TV, or
an external input.

## From a terminal

```bash
freetvos-split pip pick
freetvos-split pip
freetvos-split pip-swap
freetvos-split pip-corner
freetvos-split pip-off
```
