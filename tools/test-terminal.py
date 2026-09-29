#!/usr/bin/env python3
"""Check the Terminal tile: Konsole full screen, FreeTVOS colours, and sudo.

Run with: python3 tools/test-terminal.py
"""
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
OVERLAY = REPO / "image/overlay"
failures = []


def check(label, got, want):
    if got == want:
        print(f"  ok   {label}")
    else:
        print(f"  FAIL {label}\n         got  {got!r}\n         want {want!r}")
        failures.append(label)


def main() -> int:
    containerfile = (REPO / "image/Containerfile").read_text()
    tile = (OVERLAY / "usr/share/applications/freetvos-terminal.desktop").read_text()
    profile = (OVERLAY / "usr/share/konsole/FreeTVOS.profile").read_text()
    scheme = (OVERLAY / "usr/share/konsole/FreeTVOS.colorscheme").read_text()
    sudoers = (OVERLAY / "etc/sudoers.d/freetvos").read_text()
    apps = (OVERLAY / "etc/freetvos/apps.conf").read_text()

    print("the tile")
    check("Konsole is installed", "      konsole \\" in containerfile, True)
    check("the tile runs the launcher",
          re.search(r"^Exec=(.*)$", tile, re.M).group(1), "/usr/bin/freetvos-terminal")
    import importlib.machinery, importlib.util
    loader = importlib.machinery.SourceFileLoader(
        "freetvos_terminal", str(OVERLAY / "usr/bin/freetvos-terminal"))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    launcher = importlib.util.module_from_spec(spec)
    loader.exec_module(launcher)
    for flag in ("--fullscreen", "--hide-menubar", "--hide-tabbar", "FreeTVOS"):
        check(f"Konsole opens with {flag}", flag in launcher.KONSOLE, True)
    import base64
    raw = base64.b64decode(launcher.STATE)
    for name in ("mainToolBar", "sessionToolbar"):
        tag = name.encode("utf-16-be")
        check(f"the saved state marks {name} hidden", raw[raw.find(tag) + len(tag)], 0)
    saved = ("[MainWindow]\n1920x1080 screen: Width=1920\nState=OLD\n\n[Other]\nState=KEEP\n")
    new = launcher.with_state(saved)
    check("the state replaces Konsole's own and nothing else",
          (new.count("State=" + launcher.STATE), "State=OLD" in new, "State=KEEP" in new,
           "1920x1080 screen: Width=1920" in new), (1, False, True, True))
    check("and is added to a file that has none", launcher.with_state("").count(launcher.STATE), 1)
    check("Konsole's own small-window tile is hidden", "\norg.kde.konsole\n" in apps, True)
    check("and the tile has its icon", (REPO / "brand/icons/freetvos-terminal.svg").is_file(), True)

    print("how it looks")
    check("the profile uses the FreeTVOS colours", "ColorScheme=FreeTVOS" in profile, True)
    check("in type that reads from across a room",
          int(re.search(r"^Font=[^,]+,(\d+)", profile, re.M).group(1)) >= 18, True)
    check("on the brand background", "[Background]\nColor=11,14,20" in scheme, True)

    print("sudo")
    check("the tv account may run anything as root with no password",
          "tv ALL=(ALL) NOPASSWD: ALL" in sudoers, True)
    check("the rule file is made unwritable and checked at build time",
          "chmod 0440 /etc/sudoers.d/freetvos && visudo -cf /etc/sudoers.d/freetvos"
          in containerfile, True)
    check("the cost is documented", "The cost of sudo without a password"
          in (REPO / "docs/TERMINAL.md").read_text(), True)

    if failures:
        print(f"\n{len(failures)} failed")
        return 1
    print("\nall checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
