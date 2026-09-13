#!/usr/bin/env python3
"""Check adding and removing services, without touching the network.

The parts worth pinning down are the ones that decide what ends up on the home
screen: which files are written and where, that removing puts it all back, that
a service added on the device wins over one of the same name in the image, and
that an icon which would be invisible on a dark tile is caught before it gets
there.

Run with: python3 tools/test-services.py
"""
import importlib.machinery
import importlib.util
import os
import sys
import tempfile
from pathlib import Path

sys.dont_write_bytecode = True

REPO = Path(__file__).resolve().parent.parent
SOURCE = REPO / "image/overlay/usr/bin/freetvos-service"
CATALOG = REPO / "image/overlay/usr/share/freetvos/service-catalog.json"

failures = []


def check(label, got, want):
    if got == want:
        print(f"  ok   {label}")
    else:
        print(f"  FAIL {label}\n         got  {got!r}\n         want {want!r}")
        failures.append(label)


def load(root: Path):
    os.environ["XDG_CONFIG_HOME"] = str(root / "conf")
    os.environ["XDG_DATA_HOME"] = str(root / "data")
    os.environ["FREETVOS_CATALOG"] = str(CATALOG)
    loader = importlib.machinery.SourceFileLoader("freetvos_service",
                                                  str(SOURCE))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


COLOURED_SVG = (b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24">'
                b'<path fill="#1DB954" d="M0 0h24v24z"/></svg>')
BLACK_SVG = (b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24">'
             b'<path fill="#000" d="M0 0h24v24z"/></svg>')
# The one that got through the first time: no fill attribute at all, which
# renders black.
IMPLICIT_SVG = (b'<svg xmlns="http://www.w3.org/2000/svg" width="32" '
                b'height="32"><path d="M0 0h24v24z"/></svg>')


def main() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        svc = load(root)

        print("the catalogue")
        entries = svc.catalog()
        check("has entries", len(entries) > 10, True)
        ids = [e["id"] for e in entries]
        check("ids are unique", len(ids), len(set(ids)))
        check("every entry is complete",
              [e["id"] for e in entries
               if not (e.get("name") and e.get("url", "").startswith("https://")
                       and e.get("category"))], [])
        check("music is grouped",
              sorted(e["id"] for e in entries if e["group"] == "Music")[:3],
              ["applemusic", "bandcamp", "deezer"])

        print("naming")
        check("slug", svc.slug("Apple Music"), "applemusic")
        check("slug drops punctuation", svc.slug("Paramount+ (US)"),
              "paramountus")
        check("slug never empty", svc.slug("!!!"), "service")

        print("adding one")
        entry = next(e for e in entries if e["id"] == "spotify")
        svc.add(entry["id"], entry["name"], entry["url"], entry["drm"],
                entry["category"], offline=True)
        conf = Path(os.environ["XDG_CONFIG_HOME"])
        data = Path(os.environ["XDG_DATA_HOME"])
        definition = conf / "freetvos/webapps/spotify.app"
        desktop = data / "applications/freetvos-spotify.desktop"
        icon = data / "icons/hicolor/scalable/apps/freetvos-spotify.svg"
        check("definition written", definition.exists(), True)
        check("tile written", desktop.exists(), True)
        check("lettermark drawn", icon.exists(), True)
        check("the letter is the service's own", "S" in icon.read_text(), True)
        body = definition.read_text()
        check("address", 'URL="https://open.spotify.com/"' in body, True)
        check("marked as needing Widevine", 'DRM="yes"' in body, True)
        check("carries a browser agent", "CrOS" in body, True)
        entry_text = desktop.read_text()
        check("tile runs the shared launcher",
              "Exec=/usr/bin/freetvos-webapp spotify" in entry_text, True)
        check("tile is offered to the television",
              "X-KDE-FormFactor=tv" in entry_text, True)

        print("what the system now knows about")
        have = svc.installed()
        check("listed as added", have["spotify"]["source"], "added")
        check("with its name", have["spotify"]["name"], "Spotify")

        print("a service added by address")
        svc.add(svc.slug("My Jellyfin"), "My Jellyfin",
                "https://jellyfin.local:8096", "no",
                "AudioVideo;Video;Player;", offline=True)
        check("its own id", (conf / "freetvos/webapps/myjellyfin.app").exists(),
              True)
        check("no browser agent when it needs no Widevine",
              "USER_AGENT" in (conf / "freetvos/webapps/myjellyfin.app").read_text(),
              False)

        print("removing")
        check("removed", svc.remove("spotify"), True)
        check("definition gone", definition.exists(), False)
        check("tile gone", desktop.exists(), False)
        check("icon gone", icon.exists(), False)
        check("removing twice is not a crash", svc.remove("spotify"), False)
        check("the other one is untouched",
              "myjellyfin" in svc.installed(), True)

        print("icons that would vanish on a dark tile")
        check("a coloured drawing is left alone",
              svc.plate_dark_svg(COLOURED_SVG), None)
        plated = svc.plate_dark_svg(BLACK_SVG)
        check("explicit black is plated", b'fill="#E6EAF2"' in plated, True)
        check("the original is kept inside", b"M0 0h24v24z" in plated, True)
        check("its own coordinates are carried over",
              b'viewBox="0 0 24 24"' in plated, True)
        implicit = svc.plate_dark_svg(IMPLICIT_SVG)
        check("no fill at all is also black", implicit is not None, True)
        check("size attributes become a viewBox",
              b'viewBox="0 0 32 32"' in implicit, True)

        print("measuring what was downloaded")
        png = (b"\x89PNG\r\n\x1a\n" + b"\x00\x00\x00\x0dIHDR"
               + (180).to_bytes(4, "big") + (180).to_bytes(4, "big"))
        check("png size is read from the header", svc._kind(png, ""),
              ("png", 180))
        check("svg counts as large enough",
              svc._kind(COLOURED_SVG, "")[0], "svg")
        check("an ico is refused", svc._kind(b"\x00\x00\x01\x00", "")[0], None)
        check("a 180 pixel icon lands in the right bucket",
              svc._size_dir(180), "128x128")
        check("a small one is not pretended to be big",
              svc._size_dir(48), "64x64")

        print("the image and the catalogue")
        import json
        shipped = sorted(f.stem for f in (REPO / "webapps/apps.d").glob("*.app"))
        offered = [s["id"] for g in json.loads(CATALOG.read_text())["groups"]
                   for s in g["services"]]
        # A service in both would be offered for adding while it is already on
        # the home screen, and adding it would write a second copy over the
        # first. Prime Video, Paramount+ and Peacock moved from one to the other.
        check("nothing is both built in and offered for adding",
              sorted(set(shipped) & set(offered)), [])
        check("every built-in service has its own icon",
              [s for s in shipped
               if not (REPO / f"brand/icons/freetvos-{s}.svg").exists()], [])

        print("typing on a television")
        sys.path.insert(0, str(REPO / "image/overlay/usr/share/freetvos"))
        import servicesui, mediaui
        # Both fields were only fillable with a keyboard plugged in: focusing
        # them was meant to raise the system's on-screen keyboard, which never
        # draws on this shell. A placeholder left unfilled would ship a page
        # whose Enter key calls a function that does not exist.
        for label, body in (("add by web address", servicesui.CUSTOM_BODY),
                            ("jellyfin server address", mediaui.ADDRESS_BODY)):
            check(f"{label} carries the page's own keyboard",
                  "function tvkeyboard" in body and "__KB__" not in body, True)
            check(f"{label} opens it from the field",
                  "tvkeyboard({" in body, True)

        print("the jellyfin tile")
        jf_loader = importlib.machinery.SourceFileLoader(
            "freetvos_jellyfin", str(REPO / "image/overlay/usr/bin/freetvos-jellyfin"))
        jf_spec = importlib.util.spec_from_loader(jf_loader.name, jf_loader)
        jf = importlib.util.module_from_spec(jf_spec)
        jf_loader.exec_module(jf)
        jf.ACCOUNT = root / "media/jellyfin.json"
        check("with no server it asks for one, rather than opening nothing",
              jf.target()[-2:], ["--start", "/jellyfin-address"])
        jf.ACCOUNT.parent.mkdir(parents=True, exist_ok=True)
        jf.ACCOUNT.write_text('{"base": "http://jf.local:8096/"}')
        check("with a server it opens that server's web client",
              jf.target()[-2:], ["jellyfin", "http://jf.local:8096/web/"])
        jf.ACCOUNT.write_text("{broken")
        check("a damaged sign-in file is treated as none",
              jf.target()[-1], "/jellyfin-address")

    print()
    if failures:
        print(f"{len(failures)} check(s) failed")
        return 1
    print("all checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
