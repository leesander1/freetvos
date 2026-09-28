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
import time
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

        print("back and the keyboard")
        nav = tvui.NAV_JS
        check("a page can leave", "fetch('/__leave'" in nav, True)
        check("back falls back to leaving when there is nowhere to go",
              "if (location.href === before) tvleave();" in nav, True)
        check("Backspace and Escape are Back, and leave a page with no Back",
              "e.key === 'Backspace' || e.key === 'Escape'" in nav
              and "(onBack || tvleave)();" in nav, True)
        kb = tvui.KEYBOARD_JS
        check("Enter after typing on a keyboard is Done",
              "e.key === 'Enter' && typing" in kb, True)
        check("the arrows give Enter back to the on-screen keys",
              "if (e.key.startsWith('Arrow')) typing = false;" in kb, True)
        pages = "".join((UI / f).read_text() for f in
                        ("barsui.py", "sportsui.py", "setupui.py", "mediaui.py"))
        check("no page calls history.back() directly", "history.back()" in pages, False)
        check("the leave route is served before the page's own",
              '"/__leave"' in Path(tvui.__file__).read_text(), True)

        print("opening a page")
        gif = tvui.READY_GIF
        check("the ready picture is a 1x1 GIF",
              (gif[:6], int.from_bytes(gif[6:8], "little"),
               int.from_bytes(gif[8:10], "little"), gif[-1:]),
              (b"GIF89a", 1, 1, b";"))
        profile = root / "profile"
        profile.mkdir()
        for name in ("SingletonLock", "SingletonSocket"):
            (profile / name).write_text("stale")
        import subprocess as sp
        stale = sp.Popen([sys.executable, "-c", "import time; time.sleep(60)",
                          f"--user-data-dir={profile}"])
        other = sp.Popen([sys.executable, "-c", "import time; time.sleep(60)",
                          f"--user-data-dir={profile}-other"])
        time.sleep(0.3)
        tvui.close_stale_browser(profile, wait=3)
        check("a browser still holding the page's profile is closed first",
              stale.poll() is not None, True)
        check("one holding another page's profile is left alone",
              other.poll() is None, True)
        check("and its lock is cleared",
              sorted(p.name for p in profile.iterdir()), [])
        other.kill()
        other.wait()
        loading = (UI / "loading.html").read_text()
        check("pages open on the loading page, which waits for /__ready",
              '"__ready"' in loading and "location.replace(target)" in loading, True)
        check("which only follows an address on this television",
              "(localhost|127\\.0\\.0\\.1)" in loading, True)

        print("Backspace in a streaming service")
        ext = REPO / "image/overlay/usr/share/freetvos/extensions/tv-back"
        back = (ext / "back.js").read_text()
        check("it hears the key before the service can swallow it",
              "  }, true);" in back and "pending = press;" in back, True)
        check("a key the service used and that went nowhere arms a second press",
              "armedUntil = Date.now() + 2000;" in back, True)
        check("and the second press leaves, before the service sees it",
              "e.stopImmediatePropagation();\n      leave();" in back, True)
        check("never while typing", "!e.shiftKey && !typing();" in back, True)
        check("the background closes only the asker's own window",
              "chrome.windows.remove(sender.tab.windowId)" in
              (ext / "background.js").read_text(), True)
        import shutil, subprocess
        if shutil.which("node"):
            for script in ("back.js", "background.js"):
                done = subprocess.run(["node", "--check", str(ext / script)],
                                      capture_output=True)
                check(f"{script} parses", done.returncode, 0)

    if failures:
        print(f"\n{len(failures)} failed")
        return 1
    print("\nall checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
