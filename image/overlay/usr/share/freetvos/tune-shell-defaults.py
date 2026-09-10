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


COLOR_SCHEME = Path("/usr/share/color-schemes/BreezeDark.colors")
SYSTEM_KDEGLOBALS = Path("/etc/xdg/kdeglobals")


def darken_shell() -> bool:
    """Actually make Qt applications dark.

    Setting ColorScheme=BreezeDark is not enough, and this cost some time to
    work out. That key is only a label recording which scheme was chosen; the
    colours applications actually read live in [Colors:Window], [Colors:View]
    and friends, which the Colours settings page copies into kdeglobals when a
    scheme is picked. Upstream Bigscreen already sets the label, which is why
    the shell looks dark while every dialog and the settings window opened in
    light Breeze.

    So the scheme's colour groups are merged into the system kdeglobals here,
    which is what a user picking the scheme by hand would have produced.
    """
    if not COLOR_SCHEME.exists():
        print("  skip dark scheme: BreezeDark.colors missing")
        return False
    if not SYSTEM_KDEGLOBALS.exists():
        print("  skip dark scheme: /etc/xdg/kdeglobals missing")
        return False

    # Take only the [Colors:*] groups plus [WM]; the rest of a .colors file is
    # metadata that does not belong in kdeglobals.
    wanted, current = [], None
    for line in COLOR_SCHEME.read_text().splitlines():
        if line.startswith("["):
            current = line.strip()
        if current and (current.startswith("[Colors:") or current == "[WM]"):
            wanted.append(line)

    existing = SYSTEM_KDEGLOBALS.read_text()
    if "[Colors:Window]" in existing:
        print("  dark scheme already merged")
        return True

    SYSTEM_KDEGLOBALS.write_text(
        existing.rstrip("\n") + "\n\n" + "\n".join(wanted) + "\n")
    print(f"  merged {len(wanted)} lines of BreezeDark into /etc/xdg/kdeglobals")
    return True


BIGSCREEN_DEFAULTS = Path(
    "/usr/share/plasma/look-and-feel/org.kde.plasma.bigscreen/contents/defaults"
)


def darken_plasma_theme() -> bool:
    """Switch the Plasma theme to the dark one.

    Separate from the colour scheme above, and this is the piece that actually
    darkens the settings window. Kirigami and QtQuick Controls applications
    styled with the Plasma style read [Theme] name from plasmarc; the
    ColorScheme in kdeglobals governs classic widget applications. Bigscreen
    ships name=default, which is light, so the settings window stayed white
    however the colour scheme was set.
    """
    if not BIGSCREEN_DEFAULTS.exists():
        print("  skip plasma theme: look-and-feel defaults missing")
        return False
    text = BIGSCREEN_DEFAULTS.read_text()
    if "name=breeze-dark" in text:
        print("  plasma theme already dark")
        return True
    if "[plasmarc][Theme]\nname=default" not in text:
        print("  skip plasma theme: expected block not found")
        return False
    BIGSCREEN_DEFAULTS.write_text(
        text.replace("[plasmarc][Theme]\nname=default",
                     "[plasmarc][Theme]\nname=breeze-dark"))
    print("  plasma theme set to breeze-dark")
    return True


def main() -> int:
    set_bool_default(HOMESCREEN, "coloredTiles", "false")
    pin_wallpaper()
    darken_shell()
    darken_plasma_theme()
    return 0


if __name__ == "__main__":
    sys.exit(main())
