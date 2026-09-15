#!/usr/bin/env python3
"""Every FreeTVOS asset, from its SVG master. The list is docs/ASSETS.md.

  tools/gen-assets.sh              the derived SVGs, every PNG, then the check
  tools/gen-assets.sh svg          only the derived SVGs
  tools/gen-assets.sh png          only the PNGs
  python3 tools/gen-assets.py check
                                   that everything exists at the right size;
                                   standard library only, so lint runs it

Drawn by hand, and edited directly:

  brand/icons/freetvos.svg              the mark on its tile
  brand/icons/freetvos-*.svg            every service and feature tile
  brand/logo/freetvos-glyph.svg         the mark without its tile
  brand/logo/freetvos-mark-light.svg    the mark for light surfaces
  brand/logo/freetvos-small.svg         optional: the mark redrawn for 24px
                                        and below, used when it exists
  brand/splash/throbber.svg             one spinner frame

Derived, written by `svg`, committed, never edited by hand:

  brand/logo/freetvos-wordmark.svg      mark and name side by side, for dark
  brand/logo/freetvos-wordmark-light.svg                        and for light
  brand/banners/freetvos-<id>.svg       16:9, one per service in webapps/apps.d
  brand/wallpaper/freetvos-wallpaper.svg
  brand/splash/background.svg
  brand/installer/sidebar.svg, topbar.svg

Text in the derived SVGs is outlined from Noto Sans, the interface's own font,
so no PNG depends on which fonts the machine drawing it happens to have.

PNGs go under brand/png, laid out the way the image installs them where there
is such a place: brand/png/hicolor mirrors /usr/share/icons/hicolor.
"""
import math
import os
import re
import shutil
import struct
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
BRAND = REPO / "brand"
ICONS = BRAND / "icons"
LOGO = BRAND / "logo"
PNG = BRAND / "png"
APPS = REPO / "webapps/apps.d"
FONTS = Path(os.environ.get("FREETVOS_FONT_DIR", "/usr/share/fonts/google-noto"))

MARK_SIZES = (512, 256, 128, 64, 48, 32, 24, 22, 16)
TILE_SIZES = (512, 256)
THROBBER_FRAMES = 24
WORDMARK_WIDTH = 1200

# The wallpaper's lower edge: a step above the tile surface, as the wallpaper
# has always been, so the grid of tiles still separates from the ground.
WALLPAPER_BOTTOM = "#181E2A"


# ------------------------------------------------------------------ inputs ---

def brand() -> dict:
    """brand/brand.env's names and colours, the one place they are defined."""
    values = {}
    for line in (BRAND / "brand.env").read_text().splitlines():
        found = re.match(r'^(BRAND_[A-Z_]+)="([^"]*)"', line)
        if found:
            values[found.group(1)] = found.group(2)
    return values


def services() -> list:
    """(id, display name, icon) for every service shipped in the image."""
    out = []
    for path in sorted(APPS.glob("*.app")):
        text = path.read_text()

        def key(name):
            found = re.search(rf'^{name}="?([^"\n]*)"?\s*$', text, re.M)
            return found.group(1) if found else ""

        out.append((path.stem, key("NAME") or path.stem,
                    key("ICON") or f"freetvos-{path.stem}"))
    return out


def svg_size(path: Path):
    """An SVG's width and height, from its root element."""
    head = path.read_text()[:2000]
    width = re.search(r'<svg\b[^>]*\bwidth="([\d.]+)"', head)
    height = re.search(r'<svg\b[^>]*\bheight="([\d.]+)"', head)
    return float(width.group(1)), float(height.group(1))


# -------------------------------------------------------------- composing ---

def nest(path: Path, x, y, w, h, recolour=None) -> str:
    """Another master placed inside this one, as a nested <svg>."""
    text = re.sub(r"<\?xml[^>]*\?>", "", path.read_text()).strip()
    found = re.match(r"<svg\b([^>]*)>(.*)</svg>\s*$", text, re.S)
    view = re.search(r'viewBox="([^"]+)"', found.group(1)).group(1)
    body = re.sub(r"<!--.*?-->", "", found.group(2), flags=re.S)
    for old, new in (recolour or {}).items():
        body = re.sub(re.escape(old), new, body, flags=re.I)
    return (f'<svg x="{x:g}" y="{y:g}" width="{w:g}" height="{h:g}" '
            f'viewBox="{view}">{body.strip()}</svg>')


def document(w, h, body, made_from) -> str:
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w:g} {h:g}" '
            f'width="{w:g}" height="{h:g}">\n'
            f"  <!-- Written by tools/gen-assets.py from {made_from}. "
            f"Change those and run tools/gen-assets.sh; do not edit this. -->\n"
            f"{body}\n</svg>\n")


def mix(a: str, b: str, t: float) -> str:
    ca = [int(a[i:i + 2], 16) for i in (1, 3, 5)]
    cb = [int(b[i:i + 2], 16) for i in (1, 3, 5)]
    return "#" + "".join(f"{round(x + (y - x) * t):02X}" for x, y in zip(ca, cb))


def vertical(name, top, bottom, eased=False, stops=17) -> str:
    """A top-to-bottom gradient. Eased, it changes slowest at either end."""
    rows = []
    for i in range(stops):
        t = i / (stops - 1)
        e = t * t * (3 - 2 * t) if eased else t
        rows.append(f'<stop offset="{t:.4f}" stop-color="{mix(top, bottom, e)}"/>')
    return (f'<linearGradient id="{name}" x1="0" y1="0" x2="0" y2="1">'
            + "".join(rows) + "</linearGradient>")


class Type:
    """A font, for setting a line of text as outlines."""

    def __init__(self, filename: str):
        from fontTools.ttLib import TTFont
        self.path = FONTS / filename
        self.font = TTFont(str(self.path))
        self.glyphs = self.font.getGlyphSet()
        self.upm = self.font["head"].unitsPerEm
        self.cap = getattr(self.font["OS/2"], "sCapHeight", 0) or 0.714 * self.upm

    def shaped(self, text: str) -> list:
        """(glyph name, advance) with the font's own kerning when HarfBuzz is
        there to apply it, and plain advances when it is not."""
        try:
            import uharfbuzz as hb
        except ImportError:
            cmap = self.font.getBestCmap()
            return [(cmap[ord(c)], self.glyphs[cmap[ord(c)]].width) for c in text]
        font = hb.Font(hb.Face(hb.Blob.from_file_path(str(self.path))))
        buf = hb.Buffer()
        buf.add_str(text)
        buf.guess_segment_properties()
        hb.shape(font, buf, {"kern": True, "liga": True})
        return [(self.font.getGlyphName(info.codepoint), pos.x_advance)
                for info, pos in zip(buf.glyph_infos, buf.glyph_positions)]

    def width(self, text: str, size: float) -> float:
        return sum(advance for _, advance in self.shaped(text)) * size / self.upm

    def cap_height(self, size: float) -> float:
        return self.cap * size / self.upm

    def outline(self, text: str, size: float, x: float, baseline: float) -> str:
        """SVG path data for text at size px, its left edge at x."""
        from fontTools.pens.svgPathPen import SVGPathPen
        from fontTools.pens.transformPen import TransformPen

        def number(v):
            return f"{v:.1f}".rstrip("0").rstrip(".")

        scale = size / self.upm
        pen_x = x
        parts = []
        for name, advance in self.shaped(text):
            pen = SVGPathPen(self.glyphs, ntos=number)
            self.glyphs[name].draw(
                TransformPen(pen, (scale, 0, 0, -scale, pen_x, baseline)))
            parts.append(pen.getCommands())
            pen_x += advance * scale
        return " ".join(p for p in parts if p)

    def fit(self, text: str, size: float, room: float) -> float:
        """The size, made smaller if the text would not fit in room."""
        wide = self.width(text, size)
        return size if wide <= room else size * room / wide


# ----------------------------------------------------------- derived SVGs ---

def wordmark(b: dict, light: bool) -> str:
    bold = Type("NotoSans-Bold.ttf")
    ink = b["BRAND_BG"] if light else b["BRAND_TEXT"]
    mark = b["BRAND_BG"] if light else b["BRAND_ACCENT"]
    height, glyph, pad, gap, size = 240, 200, 20, 34, 150
    baseline = height / 2 + bold.cap_height(size) / 2
    text_x = pad + glyph + gap
    width = math.ceil(text_x + bold.width(b["BRAND_NAME"], size) + pad)
    body = (
        "  " + nest(LOGO / "freetvos-glyph.svg", pad, pad, glyph, glyph,
                    recolour={"#3DDC97": mark}) + "\n"
        f'  <path fill="{ink}" d="{bold.outline(b["BRAND_NAME"], size, text_x, baseline)}"/>')
    return document(width, height, body,
                    "brand/logo/freetvos-glyph.svg and BRAND_NAME, in Noto Sans Bold")


def banner(b: dict, name: str, icon: Path) -> str:
    semibold = Type("NotoSans-SemiBold.ttf")
    w, h = 1600, 900
    tile = 360
    tile_x, tile_y = 160, (h - tile) / 2
    text_x = tile_x + tile + 80
    # Title safe is the inner 90%: nothing written past 1520 across.
    size = semibold.fit(name, 110, (w - 80) - text_x)
    baseline = h / 2 + semibold.cap_height(size) / 2
    body = (
        "  <defs>" + vertical("ground", b["BRAND_SURFACE"], b["BRAND_BG"]) + "</defs>\n"
        f'  <rect width="{w}" height="{h}" fill="url(#ground)"/>\n'
        "  " + nest(icon, tile_x, tile_y, tile, tile) + "\n"
        f'  <path fill="{b["BRAND_TEXT"]}" d="{semibold.outline(name, size, text_x, baseline)}"/>\n'
        f'  <rect x="{text_x}" y="{baseline + 40:g}" width="120" height="8" rx="4" '
        f'fill="{b["BRAND_ACCENT"]}"/>')
    return document(w, h, body, f"brand/icons/{icon.name} and the service's NAME")


def wallpaper(b: dict) -> str:
    w, h = 3840, 2160
    body = (
        "  <defs>" + vertical("ground", b["BRAND_BG"], WALLPAPER_BOTTOM, eased=True)
        + "</defs>\n"
        f'  <rect width="{w}" height="{h}" fill="url(#ground)"/>')
    return document(w, h, body, "BRAND_BG: dark and flat in the upper third, "
                    "where the shell draws the clock")


def splash_background(b: dict) -> str:
    return document(1920, 1080, f'  <rect width="1920" height="1080" fill="{b["BRAND_BG"]}"/>',
                    "BRAND_BG")


def sidebar(b: dict) -> str:
    bold, regular = Type("NotoSans-Bold.ttf"), Type("NotoSans-Regular.ttf")
    w, h, glyph = 800, 600, 230
    name_size = bold.fit(b["BRAND_NAME"], 72, w - 120)
    tag = b.get("BRAND_TAGLINE", "")
    tag_size = regular.fit(tag, 28, w - 120)
    name_x = (w - bold.width(b["BRAND_NAME"], name_size)) / 2
    tag_x = (w - regular.width(tag, tag_size)) / 2
    body = (
        "  <defs>" + vertical("ground", b["BRAND_BG"], b["BRAND_SURFACE"]) + "</defs>\n"
        f'  <rect width="{w}" height="{h}" fill="url(#ground)"/>\n'
        "  " + nest(LOGO / "freetvos-glyph.svg", (w - glyph) / 2, 96, glyph, glyph) + "\n"
        f'  <path fill="{b["BRAND_TEXT"]}" d="{bold.outline(b["BRAND_NAME"], name_size, name_x, 420)}"/>\n'
        + (f'  <path fill="{b["BRAND_TEXT_DIM"]}" d="{regular.outline(tag, tag_size, tag_x, 474)}"/>'
           if tag else ""))
    return document(w, h, body, "brand/logo/freetvos-glyph.svg, BRAND_NAME and BRAND_TAGLINE")


def topbar(b: dict) -> str:
    semibold = Type("NotoSans-SemiBold.ttf")
    w, h, glyph, size = 800, 45, 33, 22
    baseline = h / 2 + semibold.cap_height(size) / 2
    body = (
        f'  <rect width="{w}" height="{h}" fill="{b["BRAND_BG"]}"/>\n'
        "  " + nest(LOGO / "freetvos-glyph.svg", 14, (h - glyph) / 2, glyph, glyph) + "\n"
        f'  <path fill="{b["BRAND_TEXT"]}" d="{semibold.outline(b["BRAND_NAME"], size, 58, baseline)}"/>')
    return document(w, h, body, "brand/logo/freetvos-glyph.svg and BRAND_NAME")


def write_svgs() -> None:
    b = brand()
    written = {
        LOGO / "freetvos-wordmark.svg": wordmark(b, light=False),
        LOGO / "freetvos-wordmark-light.svg": wordmark(b, light=True),
        BRAND / "wallpaper/freetvos-wallpaper.svg": wallpaper(b),
        BRAND / "splash/background.svg": splash_background(b),
        BRAND / "installer/sidebar.svg": sidebar(b),
        BRAND / "installer/topbar.svg": topbar(b),
    }
    banners = BRAND / "banners"
    if banners.is_dir():
        shutil.rmtree(banners)
    for app_id, name, icon in services():
        written[banners / f"freetvos-{app_id}.svg"] = banner(b, name, ICONS / f"{icon}.svg")
    for path, text in written.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
    print(f"{len(written)} derived SVGs written")


# ------------------------------------------------------------------- PNGs ---

def rasters() -> list:
    """(master, PNG, width, height, degrees) for every PNG the product uses."""
    out = []
    small = LOGO / "freetvos-small.svg"
    for s in MARK_SIZES:
        master = small if s <= 24 and small.exists() else ICONS / "freetvos.svg"
        out.append((master, PNG / f"hicolor/{s}x{s}/apps/freetvos.png", s, s, 0))
    for svg in sorted(ICONS.glob("freetvos-*.svg")):
        for s in TILE_SIZES:
            out.append((svg, PNG / f"hicolor/{s}x{s}/apps/{svg.stem}.png", s, s, 0))

    out.append((LOGO / "freetvos-mark-light.svg", PNG / "logo/freetvos-mark-light.png",
                512, 512, 0))
    for name in ("freetvos-wordmark", "freetvos-wordmark-light"):
        master = LOGO / f"{name}.svg"
        w, h = svg_size(master) if master.exists() else (6, 1)
        out.append((master, PNG / f"logo/{name}.png", WORDMARK_WIDTH,
                    round(WORDMARK_WIDTH * h / w), 0))

    out.append((LOGO / "freetvos-glyph.svg", PNG / "splash/logo.png", 640, 640, 0))
    out.append((BRAND / "splash/background.svg", PNG / "splash/background.png",
                1920, 1080, 0))
    for i in range(THROBBER_FRAMES):
        out.append((BRAND / "splash/throbber.svg", PNG / f"splash/throbber-{i + 1:04d}.png",
                    128, 128, 360 * i / THROBBER_FRAMES))

    for w, h in ((3840, 2160), (1920, 1080)):
        out.append((BRAND / "wallpaper/freetvos-wallpaper.svg",
                    PNG / f"wallpaper/{w}x{h}.png", w, h, 0))

    for app_id, _, _ in services():
        out.append((BRAND / f"banners/freetvos-{app_id}.svg",
                    PNG / f"banners/freetvos-{app_id}.png", 1600, 900, 0))

    out.append((BRAND / "installer/sidebar.svg", PNG / "installer/sidebar.png", 800, 600, 0))
    out.append((BRAND / "installer/topbar.svg", PNG / "installer/topbar.png", 800, 45, 0))
    out.append((ICONS / "freetvos.svg", PNG / "installer/volume-icon.png", 512, 512, 0))
    return out


def render(job) -> None:
    master, target, w, h, degrees = job
    target.parent.mkdir(parents=True, exist_ok=True)
    source, temporary = master, None
    if degrees:
        text = master.read_text()
        found = re.match(r"(.*?<svg\b[^>]*>)(.*)(</svg>\s*)$", text, re.S)
        vx, vy, vw, vh = (float(v) for v in
                          re.search(r'viewBox="([^"]+)"', found.group(1)).group(1).split())
        with tempfile.NamedTemporaryFile("w", suffix=".svg", delete=False) as tmp:
            tmp.write(f'{found.group(1)}<g transform="rotate({degrees:g} '
                      f'{vx + vw / 2:g} {vy + vh / 2:g})">{found.group(2)}</g>'
                      f"{found.group(3)}")
            source = temporary = Path(tmp.name)
    try:
        subprocess.run(["rsvg-convert", "-w", str(w), "-h", str(h),
                        "-o", str(target), str(source)], check=True)
    finally:
        if temporary:
            temporary.unlink()


def write_pngs() -> None:
    # From nothing each time, so a tile or service that has gone does not
    # leave its pictures behind.
    if PNG.is_dir():
        shutil.rmtree(PNG)
    jobs = rasters()
    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(render, jobs))
    print(f"{len(jobs)} PNGs written")


# ------------------------------------------------------------------ check ---

def png_size(path: Path):
    with open(path, "rb") as f:
        head = f.read(24)
    if head[:8] != b"\x89PNG\r\n\x1a\n":
        return None
    return struct.unpack(">II", head[16:24])


def check() -> int:
    problems = []
    for master in (ICONS / "freetvos.svg", LOGO / "freetvos-glyph.svg",
                   LOGO / "freetvos-mark-light.svg", BRAND / "splash/throbber.svg"):
        if not master.exists():
            problems.append(f"missing master {master.relative_to(REPO)}")
    for app_id, _, icon in services():
        if not (ICONS / f"{icon}.svg").exists():
            problems.append(f"{app_id}: no tile icon brand/icons/{icon}.svg")
    masters = set()
    jobs = rasters()
    for master, target, w, h, _ in jobs:
        if not master.exists():
            masters.add(f"missing master {master.relative_to(REPO)}")
        elif not target.exists():
            problems.append(f"missing {target.relative_to(REPO)}")
        elif png_size(target) != (w, h):
            problems.append(f"{target.relative_to(REPO)} is {png_size(target)}, "
                            f"should be {(w, h)}")
    problems = sorted(masters) + problems
    if problems:
        print("asset coverage:")
        for line in problems:
            print(f"  {line}")
        print("run tools/gen-assets.sh")
        return 1
    print(f"asset coverage ok: {len(jobs)} PNGs from {len({j[0] for j in jobs})} SVG masters")
    return 0


def main() -> int:
    what = sys.argv[1] if len(sys.argv) > 1 else "all"
    if what not in ("all", "svg", "png", "check"):
        print(__doc__)
        return 2
    if what in ("all", "svg"):
        write_svgs()
    if what in ("all", "png"):
        write_pngs()
    if what in ("all", "check"):
        return check()
    return 0


if __name__ == "__main__":
    sys.exit(main())
