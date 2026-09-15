#!/usr/bin/env python3
"""Build docs/asset-showcase.html, FreeTVOS on Screen: every generated asset
shown where it appears on the television, each marked by whether the image
reads it. Every picture is embedded, so the page is one file to open or share.

  python3 tools/asset-showcase.py

Run it after tools/gen-assets.sh; it needs Pillow. The firmware and home screens
are captures from the VM, kept in docs/images/showcase. The splash between them
is drawn here to its themes' layout, because it never reaches the VM's display.
"""
import base64
import html
import io
import re
import sys
from pathlib import Path

from PIL import Image

REPO = Path(__file__).resolve().parent.parent
OUT = REPO / "docs/asset-showcase.html"
TEMPLATE = Path(__file__).with_name("asset-showcase.html")
SHOTS = REPO / "docs/images/showcase"
PNG = REPO / "brand/png"


def uri_bytes(data: bytes, kind="image/png") -> str:
    return f"data:{kind};base64," + base64.b64encode(data).decode()


def uri(path: Path) -> str:
    return uri_bytes(path.read_bytes())


def scaled(path: Path, width: int, quality=82) -> str:
    """A screenshot, scaled and sent as JPEG: these are photographs of a
    screen, and PNG would make the page several times heavier."""
    im = Image.open(path).convert("RGB")
    if im.width > width:
        im = im.resize((width, round(im.height * width / im.width)), Image.LANCZOS)
    buf = io.BytesIO()
    im.save(buf, "JPEG", quality=quality, optimize=True, progressive=True)
    return uri_bytes(buf.getvalue(), "image/jpeg")


def splash() -> str:
    """The splash as freetvos.script and Splash.qml both lay it out: the brand
    ground, and the logo a fifth of the screen high, centred."""
    w, h = 1280, 720
    frame = Image.new("RGB", (w, h), (0x0B, 0x0E, 0x14))
    logo = Image.open(PNG / "splash/logo.png").convert("RGBA")
    side = h // 5
    logo = logo.resize((side, side), Image.LANCZOS)
    frame.paste(logo, ((w - side) // 2, (h - side) // 2), logo)
    buf = io.BytesIO()
    frame.save(buf, "PNG", optimize=True)
    return uri_bytes(buf.getvalue())


def sprite() -> str:
    frames = sorted((PNG / "splash").glob("throbber-*.png"))
    sheet = Image.new("RGBA", (128 * len(frames), 128))
    for i, f in enumerate(frames):
        sheet.alpha_composite(Image.open(f).convert("RGBA"), (128 * i, 0))
    buf = io.BytesIO()
    sheet.save(buf, "PNG", optimize=True)
    return uri_bytes(buf.getvalue()), len(frames)


def app_names() -> dict:
    names, shared = {}, {}
    for app in sorted((REPO / "webapps/apps.d").glob("*.app")):
        text = app.read_text()
        name = re.search(r'^NAME="?([^"\n]*)"?', text, re.M)
        icon = re.search(r'^ICON="?([^"\n]*)"?', text, re.M)
        icon = icon.group(1) if icon else f"freetvos-{app.stem}"
        shared.setdefault(icon, []).append(name.group(1) if name else app.stem)
    for icon, those in shared.items():
        names[icon] = those[0] if len(those) == 1 else "Meetings"
    return names


FEATURES = {
    "freetvos-add": "Apps", "freetvos-bars": "Tickers", "freetvos-hdmi": "Inputs",
    "freetvos-livetv": "Live TV", "freetvos-media": "Library",
    "freetvos-moonlight": "Game Streaming", "freetvos-pip": "Picture in picture",
    "freetvos-settings": "Settings", "freetvos-setup": "Setup",
    "freetvos-split": "Split View", "freetvos-sports": "Sports",
    "freetvos-tune": "Picture & Sound", "freetvos-applemusic": "Apple Music",
    "freetvos-spotify": "Spotify",
}


def tiles() -> str:
    names = {**FEATURES, **app_names()}
    cells = []
    for png in sorted((PNG / "hicolor/256x256/apps").glob("freetvos-*.png"),
                      key=lambda p: names.get(p.stem, p.stem).lower()):
        label = names.get(png.stem, png.stem.removeprefix("freetvos-"))
        cells.append(
            f'<figure class="tile"><img src="{uri(png)}" width="96" height="96" alt="">'
            f"<figcaption>{html.escape(label)}<code>{png.stem}</code></figcaption></figure>")
    return "\n".join(cells), len(cells)


def ladder() -> str:
    rows = []
    for s in (512, 256, 128, 64, 48, 32, 24, 22, 16):
        png = PNG / f"hicolor/{s}x{s}/apps/freetvos.png"
        shown = min(s, 128)
        zoom = f'<img class="px" src="{uri(png)}" width="{s * 4}" height="{s * 4}" alt="">' \
            if s <= 32 else ""
        master = "small" if s <= 24 else "full"
        rows.append(
            f'<div class="rung{" small" if s <= 32 else ""}">'
            f'<div class="actual"><img src="{uri(png)}" width="{shown}" height="{shown}" alt=""></div>'
            f"{zoom}"
            f'<div class="meta"><b>{s}</b><span>{master} master</span></div></div>')
    return "\n".join(rows)


def banners() -> str:
    names = app_names()
    cells = []
    for png in sorted((PNG / "banners").glob("*.png")):
        app = png.stem.removeprefix("freetvos-")
        app_file = REPO / f"webapps/apps.d/{app}.app"
        name = re.search(r'^NAME="?([^"\n]*)"?', app_file.read_text(), re.M).group(1)
        im = Image.open(png).convert("RGB").resize((800, 450), Image.LANCZOS)
        buf = io.BytesIO()
        im.save(buf, "PNG", optimize=True)
        cells.append(f'<figure class="banner"><img src="{uri_bytes(buf.getvalue())}" '
                     f'width="800" height="450" alt="{html.escape(name)} banner" loading="lazy">'
                     f"<figcaption><code>{png.name}</code></figcaption></figure>")
    return "\n".join(cells), len(cells)


def count_pngs() -> int:
    return len(list(PNG.rglob("*.png")))


def masters() -> int:
    return len([p for p in (REPO / "brand").rglob("*.svg")])


spin, frames = sprite()
tile_html, tile_count = tiles()
banner_html, banner_count = banners()
wordmark = uri(PNG / "logo/freetvos-wordmark.png")

page = TEMPLATE.read_text()
values = {
    "WORDMARK": wordmark,
    "WORDMARK_LIGHT": uri(PNG / "logo/freetvos-wordmark-light.png"),
    "MARK_LIGHT": uri(PNG / "logo/freetvos-mark-light.png"),
    "SPLASH_LOGO": uri(PNG / "splash/logo.png"),
    "SHOT_BOOT": scaled(SHOTS / "firmware.png", 1280),
    "SHOT_SESSION": splash(),
    "SHOT_HOME": scaled(SHOTS / "home.png", 1280),
    "WALLPAPER": scaled(PNG / "wallpaper/1920x1080.png", 960, 90),
    "SIDEBAR": uri(PNG / "installer/sidebar.png"),
    "TOPBAR": uri(PNG / "installer/topbar.png"),
    "VOLUME": uri(PNG / "installer/volume-icon.png"),
    "SPRITE": spin,
    "FRAMES": str(frames),
    "SPRITE_WIDTH": str(128 * frames),
    "LADDER": ladder(),
    "TILES": tile_html,
    "TILE_COUNT": str(tile_count),
    "BANNERS": banner_html,
    "BANNER_COUNT": str(banner_count),
    "PNG_COUNT": str(count_pngs()),
    "SVG_COUNT": str(masters()),
}
for key, value in values.items():
    page = page.replace("{{" + key + "}}", value)
left = re.findall(r"\{\{[A-Z_]+\}\}", page)
assert not left, left
OUT.write_text(page)
print(f"wrote {OUT.relative_to(REPO)} ({OUT.stat().st_size / 1e6:.1f} MB): {tile_count} tiles, "
      f"{banner_count} banners, {frames} spinner frames")
