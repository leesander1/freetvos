#!/usr/bin/env python3
"""Generate the FreeTVOS wallpaper. Standard library only.

Deliberately a dark, near-flat vertical gradient rather than a photograph. A
busy wallpaper behind a tile grid makes the focus ring hard to pick out, and on
a remote-driven interface knowing which tile is selected is the single most
important affordance on screen. Dark also suits a television in a dim room and
avoids the bloom that a bright field produces on OLED.

Rows are uniform, so each is one buffer multiplication rather than a per-pixel
loop. That keeps a 4K image well under a second without any imaging library.
"""
import struct
import sys
import zlib

TOP = (0x0B, 0x0E, 0x14)
BOTTOM = (0x18, 0x1E, 0x2A)


def render(w: int, h: int) -> bytes:
    raw = bytearray()
    for y in range(h):
        t = y / max(1, h - 1)
        # Eased rather than linear: a straight ramp bands visibly across a
        # large flat area, and the curve keeps the change slowest where the
        # tile row sits.
        e = t * t * (3 - 2 * t)
        px = bytes((
            round(TOP[0] + (BOTTOM[0] - TOP[0]) * e),
            round(TOP[1] + (BOTTOM[1] - TOP[1]) * e),
            round(TOP[2] + (BOTTOM[2] - TOP[2]) * e),
            255,
        ))
        raw.append(0)          # PNG filter type 0 for this scanline
        raw += px * w
    return bytes(raw)


def write_png(path: str, w: int, h: int, raw: bytes) -> None:
    def chunk(tag: bytes, data: bytes) -> bytes:
        return (struct.pack(">I", len(data)) + tag + data
                + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF))

    png = (b"\x89PNG\r\n\x1a\n"
           + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 6, 0, 0, 0))
           + chunk(b"IDAT", zlib.compress(raw, 9))
           + chunk(b"IEND", b""))
    with open(path, "wb") as f:
        f.write(png)


def main() -> int:
    out = sys.argv[1]
    w, h = int(sys.argv[2]), int(sys.argv[3])
    write_png(out, w, h, render(w, h))
    print(f"wrote {out} ({w}x{h})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
