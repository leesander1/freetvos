#!/usr/bin/env python3
"""Check that Bigscreen is coloured FreeTVOS rather than Breeze blue.

Plasma reads colours from three places, and each once kept Breeze's blue: the
system kdeglobals, Bigscreen's own look-and-feel (which Plasma copies over the
system defaults), and the dark Plasma theme's own colours file. The build fills
all three from one scheme, FreeTVOS.colors.

Run with: python3 tools/test-theme.py
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


def groups(text):
    out, current = {}, None
    for line in text.splitlines():
        if line.startswith("["):
            current = line.strip()
            out[current] = {}
        elif current and "=" in line and not line.startswith("#"):
            key, _, value = line.partition("=")
            out[current][key] = value
    return out


def main() -> int:
    scheme_text = (OVERLAY / "usr/share/color-schemes/FreeTVOS.colors").read_text()
    scheme = groups(scheme_text)
    print("the scheme")
    check("no Breeze blue left anywhere",
          re.findall(r"61,174,233|30,87,116|29,153,243", scheme_text), [])
    check("highlight, focus and hover are the brand accent",
          {scheme["[Colors:Selection]"]["BackgroundNormal"],
           scheme["[Colors:View]"]["DecorationFocus"],
           scheme["[Colors:View]"]["DecorationHover"]}, {"61,220,151"})
    check("pages are the brand background", scheme["[Colors:Window]"]["BackgroundNormal"],
          "11,14,20")
    check("writing on a selection is dark, since white on the accent is not legible",
          scheme["[Colors:Selection]"]["ForegroundNormal"], "11,14,20")
    for group in ("[Colors:Button]", "[Colors:View]", "[Colors:Window]",
                  "[Colors:Selection]", "[Colors:Tooltip]", "[Colors:Complementary]",
                  "[Colors:Header]", "[WM]", "[General]"):
        check(f"has {group}", group in scheme, True)
    check("it is named FreeTVOS", scheme["[General]"].get("ColorScheme"), "FreeTVOS")

    print("where Plasma reads colours")
    kdeglobals = (OVERLAY / "etc/xdg/kdeglobals").read_text()
    check("the system default names it", "ColorScheme=FreeTVOS" in kdeglobals, True)
    lnf = (OVERLAY / "usr/share/plasma/look-and-feel/org.freetvos.bigscreen/"
           "contents/defaults").read_text()
    check("FreeTVOS's look-and-feel names it", "ColorScheme=FreeTVOS" in lnf, True)
    tune = (OVERLAY / "usr/share/freetvos/tune-shell-defaults.py").read_text()
    check("the build merges it into kdeglobals",
          'COLOR_SCHEME = Path("/usr/share/color-schemes/FreeTVOS.colors")' in tune, True)
    check("the build points Bigscreen's look-and-feel at it",
          'text.replace("ColorScheme=BreezeDark", "ColorScheme=FreeTVOS")' in tune, True)
    check("the build recolours the dark Plasma theme with it",
          "PLASMA_DARK_COLORS.write_text(COLOR_SCHEME.read_text())" in tune
          and "colour_plasma_theme()" in tune.split("def main")[1], True)

    if failures:
        print(f"\n{len(failures)} failed")
        return 1
    print("\nall checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
