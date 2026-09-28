#!/usr/bin/env python3
"""Two fixes to Bigscreen's home screen, patched into its shipped QML.

Start the rows right under the clock when nothing sits above Applications, and
keep the settings panel's view of coloured tiles in step with what is saved
(see the last edit).

Run at image build time. Bigscreen starts its rows halfway down the screen, which
leaves room for Favorites and Recent above Applications. With neither, that room
is an empty band between the clock and the first row of apps, which is what a
fresh television shows.

The change is three small edits to the shipped QML: the launcher says whether
any row sits above Applications, the menu passes that up, and the home screen
uses the height right after the header when there is none. Each edit checks
that the code it replaces is still there and fails the build if not, so an
upstream change to these files is found at build time rather than as a home
screen quietly laid out wrong.
"""
import sys
from pathlib import Path

UI = Path("/usr/share/plasma/plasmoids/org.kde.bigscreen.homescreen/contents/ui")

EDITS = [
    (UI / "launcher/LauncherHome.qml",
     "    property real startY\n",
     "    property real startY\n\n"
     "    // FreeTVOS: whether any row sits above Applications. Without one the\n"
     "    // home screen starts the rows under the clock instead of halfway down.\n"
     "    readonly property bool hasRowsAboveApps: favAppsView.visible || recentView.visible\n"),
    (UI / "launcher/LauncherMenu.qml",
     "    readonly property bool scrolledDown: launcherHome.scrolledDown\n",
     "    readonly property bool scrolledDown: launcherHome.scrolledDown\n"
     "    readonly property bool hasRowsAboveApps: launcherHome.hasRowsAboveApps\n"),
    (UI / "HomeScreen.qml",
     "            const desiredY = (parent.height / 2);\n",
     "            // FreeTVOS: halfway down only when Favorites or Recent fill it.\n"
     "            const desiredY = launcher.hasRowsAboveApps ? (parent.height / 2) : minY;\n"),
    # Bigscreen's settings panel asks the home screen over D-Bus whether tiles
    # are coloured, and the D-Bus side answers from its own default, "yes",
    # because the home screen only ever copies D-Bus values into its settings
    # and never the other way. The panel then showed coloured tiles as on, and
    # opening it turned them on: FreeTVOS icons are light art on dark tiles, so
    # most tiles went white. Telling the D-Bus side the saved values at startup
    # makes the panel show the truth, and its switch still works.
    (UI / "main.qml",
     "        function onUseWallpaperBlurChanged(wallpaperBlur) {\n"
     "            Plasmoid.configuration.wallpaperBlur = wallpaperBlur;\n"
     "        }\n"
     "    }\n",
     "        function onUseWallpaperBlurChanged(wallpaperBlur) {\n"
     "            Plasmoid.configuration.wallpaperBlur = wallpaperBlur;\n"
     "        }\n"
     "    }\n\n"
     "    // FreeTVOS: tell the D-Bus side what is saved, so the settings panel\n"
     "    // reads the real state instead of its own default.\n"
     "    QtObject {\n"
     "        Component.onCompleted: {\n"
     "            BigLauncherDbusAdapterInterface.useColoredTiles(Plasmoid.configuration.coloredTiles);\n"
     "            BigLauncherDbusAdapterInterface.useWallpaperBlur(Plasmoid.configuration.wallpaperBlur);\n"
     "        }\n"
     "    }\n"),
]


def main() -> int:
    for path, old, new in EDITS:
        text = path.read_text()
        if new in text:
            print(f"  already patched {path.name}")
            continue
        if text.count(old) != 1:
            print(f"cannot patch {path}: the expected code is not there once",
                  file=sys.stderr)
            return 1
        path.write_text(text.replace(old, new))
        print(f"  patched {path.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
