#!/usr/bin/env python3
"""Change shell defaults that are only reachable as packaged defaults.

These live in KConfigXT schema files rather than in any config a build can
write, because the per-user config that would override them is generated on
first login with applet ids that do not exist yet at build time. Editing the
default in the shipped schema is the only deterministic point of control.
"""
import re
import sys
from pathlib import Path

HOMESCREEN = Path(
    "/usr/share/plasma/plasmoids/org.kde.bigscreen.homescreen"
    "/contents/config/main.xml"
)


def set_bool_default(path: Path, entry: str, value: str) -> bool:
    if not path.exists():
        print(f"  skip {entry}: {path} missing")
        return False
    text = path.read_text()
    pattern = re.compile(
        rf'(<entry name="{entry}" type="Bool">\s*<default>)(true|false)(</default>)'
    )
    new, n = pattern.subn(rf'\g<1>{value}\g<3>', text)
    if not n:
        print(f"  skip {entry}: default not found in the expected shape")
        return False
    path.write_text(new)
    print(f"  {entry} default -> {value}")
    return True


LAYOUT = Path(
    "/usr/share/plasma/look-and-feel/org.kde.plasma.bigscreen"
    "/contents/layouts/org.kde.plasma.bigscreen-layout.js"
)


def pin_wallpaper() -> bool:
    """Replace the wallpaper slideshow with one fixed image.

    Bigscreen ships a slideshow over the whole of /usr/share/wallpapers, so the
    background changes every eight minutes and differs between boots. That is
    why the wallpaper appeared to change on its own. It also defeats the point
    of a dark ground: whichever bright Fedora wallpaper comes up next makes the
    focus ring hard to see.
    """
    if not LAYOUT.exists():
        print("  skip wallpaper: layout script missing")
        return False
    text = LAYOUT.read_text()
    if 'org.kde.slideshow' not in text:
        print("  skip wallpaper: slideshow block not found")
        return False
    text = text.replace(
        'desk.wallpaperPlugin = "org.kde.slideshow";',
        'desk.wallpaperPlugin = "org.kde.image";')
    text = text.replace(
        'desk.currentConfigGroup = new Array("Wallpaper","org.kde.slideshow","General");',
        'desk.currentConfigGroup = new Array("Wallpaper","org.kde.image","General");')
    text = re.sub(r'\s*desk\.writeConfig\("SlideInterval",[^)]*\);', '', text)
    text = text.replace(
        'desk.writeConfig("SlidePaths", "/usr/share/wallpapers/");',
        'desk.writeConfig("Image", "/usr/share/wallpapers/FreeTVOS/");')
    LAYOUT.write_text(text)
    print("  wallpaper pinned to FreeTVOS")
    return True


def main() -> int:
    set_bool_default(HOMESCREEN, "coloredTiles", "false")
    pin_wallpaper()
    return 0


if __name__ == "__main__":
    sys.exit(main())
