#!/usr/bin/env python3
"""Render the boot-splash mark to PNG, using only the standard library.

Plymouth's script module draws images, not shapes. The obvious workarounds are
both bad: scaling a text glyph to fake a rectangle depends on the font having
that glyph and on how the driver renders it, and adding a rasteriser to the
build pulls in librsvg and its font stack for one picture.

The mark is rectangles and one triangle, so rendering it directly is a few
dozen lines and removes both dependencies. Supersampled 4x and box-filtered
down, which is what keeps the triangle's edge from stairstepping.
"""
import struct
import sys
import zlib

SS = 4  # supersampling factor


def parse_hex(c: str) -> tuple[int, int, int]:
    c = c.lstrip("#")
    return int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16)


class Canvas:
    def __init__(self, w: int, h: int):
        self.w, self.h = w * SS, h * SS
        self.px = bytearray(self.w * self.h * 4)  # RGBA, transparent

    def rect(self, x, y, w, h, rgb, radius=0):
        x, y, w, h, radius = (int(v * SS) for v in (x, y, w, h, radius))
        r, g, b = rgb
        for yy in range(max(0, y), min(self.h, y + h)):
            for xx in range(max(0, x), min(self.w, x + w)):
                if radius:
                    # Only test the corner quadrants; the rest is a plain fill.
                    dx = dy = 0
                    if xx < x + radius:
                        dx = x + radius - xx
                    elif xx >= x + w - radius:
                        dx = xx - (x + w - radius - 1)
                    if yy < y + radius:
                        dy = y + radius - yy
                    elif yy >= y + h - radius:
                        dy = yy - (y + h - radius - 1)
                    if dx and dy and dx * dx + dy * dy > radius * radius:
                        continue
                i = (yy * self.w + xx) * 4
                self.px[i:i + 4] = bytes((r, g, b, 255))

    def triangle(self, p1, p2, p3, rgb):
        pts = [(int(x * SS), int(y * SS)) for x, y in (p1, p2, p3)]
        r, g, b = rgb
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        (x1, y1), (x2, y2), (x3, y3) = pts
        det = (y2 - y3) * (x1 - x3) + (x3 - x2) * (y1 - y3)
        if det == 0:
            return
        for yy in range(max(0, min(ys)), min(self.h, max(ys) + 1)):
            for xx in range(max(0, min(xs)), min(self.w, max(xs) + 1)):
                a = ((y2 - y3) * (xx - x3) + (x3 - x2) * (yy - y3)) / det
                bb = ((y3 - y1) * (xx - x3) + (x1 - x3) * (yy - y3)) / det
                c = 1 - a - bb
                if a >= 0 and bb >= 0 and c >= 0:
                    i = (yy * self.w + xx) * 4
                    self.px[i:i + 4] = bytes((r, g, b, 255))

    def downsample(self) -> tuple[int, int, bytearray]:
        ow, oh = self.w // SS, self.h // SS
        out = bytearray(ow * oh * 4)
        n = SS * SS
        for y in range(oh):
            for x in range(ow):
                acc = [0, 0, 0, 0]
                for sy in range(SS):
                    row = (y * SS + sy) * self.w
                    for sx in range(SS):
                        i = (row + x * SS + sx) * 4
                        acc[0] += self.px[i]
                        acc[1] += self.px[i + 1]
                        acc[2] += self.px[i + 2]
                        acc[3] += self.px[i + 3]
                o = (y * ow + x) * 4
                out[o:o + 4] = bytes(v // n for v in acc)
        return ow, oh, out


def write_png(path: str, w: int, h: int, rgba: bytearray) -> None:
    raw = bytearray()
    for y in range(h):
        raw.append(0)  # filter type 0
        raw += rgba[y * w * 4:(y + 1) * w * 4]

    def chunk(tag: bytes, data: bytes) -> bytes:
        return (struct.pack(">I", len(data)) + tag + data
                + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF))

    png = (b"\x89PNG\r\n\x1a\n"
           + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 6, 0, 0, 0))
           + chunk(b"IDAT", zlib.compress(bytes(raw), 9))
           + chunk(b"IEND", b""))
    with open(path, "wb") as f:
        f.write(png)


def main() -> int:
    out = sys.argv[1] if len(sys.argv) > 1 else "logo.png"
    size = 512
    accent = parse_hex("#3DDC97")
    ground = parse_hex("#0B0E14")

    c = Canvas(size, size)
    # Screen, play triangle knocked out of it, stand and foot: the same mark as
    # the icon set, so boot and home screen agree.
    c.rect(40, 78, 432, 280, accent, radius=56)
    c.triangle((214, 152), (214, 284), (322, 218), ground)
    c.rect(238, 358, 36, 44, accent)
    c.rect(168, 396, 176, 36, accent, radius=18)

    w, h, px = c.downsample()
    write_png(out, w, h, px)
    print(f"wrote {out} ({w}x{h})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
