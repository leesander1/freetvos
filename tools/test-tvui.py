#!/usr/bin/env python3
"""Check the pictures the television's own pages serve from disk.

The pages are served over http to a browser that may not read files itself, so
tvui hands pictures out by name. Worth pinning down: that a name only ever
reaches the directory meant for it, and that the setup wizard asks for a
wordmark the image actually ships.

Run with: python3 tools/test-tvui.py
"""
import os
import re
import sys
import tempfile
from pathlib import Path

sys.dont_write_bytecode = True

REPO = Path(__file__).resolve().parent.parent
UI = REPO / "image/overlay/usr/share/freetvos"

failures = []


def check(label, got, want):
    if got == want:
        print(f"  ok   {label}")
    else:
        print(f"  FAIL {label}\n         got  {got!r}\n         want {want!r}")
        failures.append(label)


def main() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        brand = root / "brand"
        brand.mkdir()
        (brand / "freetvos-wordmark.svg").write_text("<svg/>")
        (brand / "notes.txt").write_text("not a picture")
        (root / "secret.svg").write_text("<svg/>")
        os.environ["FREETVOS_BRAND_DIR"] = str(brand)
        sys.path.insert(0, str(UI))
        import tvui
        import setupui

        print("brand pictures")
        found, ctype = tvui.find_brand("/brand/freetvos-wordmark.svg")
        check("the wordmark, as an SVG", (found == brand / "freetvos-wordmark.svg", ctype),
              (True, "image/svg+xml"))
        check("nothing beside the brand directory", tvui.find_brand("/brand/../secret.svg"),
              (None, None))
        check("nothing that is not a picture", tvui.find_brand("/brand/notes.txt"), (None, None))
        check("nothing that is not there", tvui.find_brand("/brand/missing.svg"), (None, None))

        print("the setup wizard")
        asked = re.search(r'src="/brand/([^"]+)"', setupui.WELCOME_BODY)
        check("the first page asks for the wordmark", asked and asked.group(1),
              "freetvos-wordmark.svg")
        containerfile = (REPO / "image/Containerfile").read_text()
        check("the image puts it where it is served from",
              "COPY brand/logo/freetvos-wordmark.svg "
              "/usr/share/freetvos/brand/freetvos-wordmark.svg" in containerfile, True)
        check("and the file exists", (REPO / "brand/logo/freetvos-wordmark.svg").is_file(), True)

    if failures:
        print(f"\n{len(failures)} failed")
        return 1
    print("\nall checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
