#!/usr/bin/env python3
"""Check pinning from the remote, offline.

Two halves. The helper Chromium starts when the pin panel asks: that it takes
the service from the browser that started it and never from the page, knows a
page it has already pinned when the address is spelled differently, and refuses
what it should. And freetvos-pin, now that what it writes can come from a web
page: a name that tries to run a command or add a line to the desktop entry, an
address with a space in it, two episodes with the same name.

Pages and posters come from a small server on this machine, so nothing here
reaches the internet.

Run with: python3 tools/test-pin.py
"""
import base64
import hashlib
import importlib.machinery
import importlib.util
import json
import os
import shutil
import struct
import subprocess
import sys
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

sys.dont_write_bytecode = True

REPO = Path(__file__).resolve().parent.parent
HOST = REPO / "image/overlay/usr/bin/freetvos-pin-host"
PIN = REPO / "image/overlay/usr/bin/freetvos-pin"
EXTENSION = REPO / "image/overlay/usr/share/freetvos/extensions/tv-pin"
REGISTRATION = REPO / "image/overlay/etc/chromium/native-messaging-hosts/org.freetvos.pin.json"

PNG = bytes.fromhex("89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c489"
                    "0000000d49444154789c6360000002000154a24f5d0000000049454e44ae426082")

failures = []


def check(label, got, want):
    if got == want:
        print(f"  ok   {label}")
    else:
        print(f"  FAIL {label}\n         got  {got!r}\n         want {want!r}")
        failures.append(label)


class Pages(BaseHTTPRequestHandler):
    """Every page advertises a poster, the way a service's title page does."""

    def do_GET(self):
        if self.path.startswith("/poster.png"):
            body, kind = PNG, "image/png"
        else:
            port = self.server.server_address[1]
            body = (f'<html><head><meta property="og:image" '
                    f'content="http://127.0.0.1:{port}/poster.png"></head></html>').encode()
            kind = "text/html"
        self.send_response(200)
        self.send_header("Content-Type", kind)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


def load_host():
    loader = importlib.machinery.SourceFileLoader("freetvos_pin_host", str(HOST))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


def frame(obj):
    data = json.dumps(obj).encode()
    return struct.pack("=I", len(data)) + data


def unframe(raw):
    if len(raw) < 4:
        return None
    (length,) = struct.unpack("=I", raw[:4])
    return json.loads(raw[4:4 + length])


def main() -> int:
    tmp = Path(tempfile.mkdtemp(prefix="freetvos-pin-test-"))
    server = ThreadingHTTPServer(("127.0.0.1", 0), Pages)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    site = f"http://127.0.0.1:{server.server_address[1]}"
    try:
        return run(tmp, site)
    finally:
        server.shutdown()
        shutil.rmtree(tmp, ignore_errors=True)


def run(tmp: Path, site: str) -> int:
    config, data, system = tmp / "config", tmp / "data", tmp / "system-webapps"
    for app in ("netflix", "youtube"):
        (system).mkdir(parents=True, exist_ok=True)
        (system / f"{app}.app").write_text(f'NAME="{app}"\nURL="https://{app}.example"\n')
    (config / "freetvos/webapps").mkdir(parents=True)
    (config / "freetvos/webapps/myjellyfin.app").write_text('NAME="Jellyfin"\n')

    # The helper starts freetvos-pin directly, and the file in the repository is
    # not marked executable until the image build does it.
    wrapper = tmp / "pin-cmd"
    wrapper.write_text(f'#!/bin/sh\nexec bash "{PIN}" "$@"\n')
    wrapper.chmod(0o755)

    env = {
        "HOME": str(tmp), "XDG_CONFIG_HOME": str(config), "XDG_DATA_HOME": str(data),
        "FREETVOS_SYSTEM_WEBAPPS": str(system), "FREETVOS_TMDB_CONF": str(tmp / "none.conf"),
        "FREETVOS_PIN_CMD": str(wrapper), "FREETVOS_PIN_HOST_PROC": str(tmp / "proc"),
    }
    os.environ.update(env)
    host = load_host()
    pins, desktop = config / "freetvos/pins.d", data / "applications"

    def pin_cli(*args):
        return subprocess.run(["bash", str(PIN), *args], capture_output=True, text=True,
                              env={**os.environ, "PATH": os.environ.get("PATH", "")},
                              cwd=tmp)

    print("the extension and the helper agree on who may ask")
    manifest = json.loads((EXTENSION / "manifest.json").read_text())
    digest = hashlib.sha256(base64.b64decode(manifest["key"])).hexdigest()[:32]
    ext_id = "".join(chr(ord("a") + int(c, 16)) for c in digest)
    registration = json.loads(REGISTRATION.read_text())
    check("the registration admits the extension's own ID",
          registration["allowed_origins"], [f"chrome-extension://{ext_id}/"])
    check("and the helper checks for the same one", host.EXTENSION_ORIGIN,
          f"chrome-extension://{ext_id}/")
    check("the registration starts this helper", registration["path"],
          "/usr/bin/freetvos-pin-host")
    check("the extension may reach it", manifest["permissions"], ["nativeMessaging"])
    if shutil.which("node"):
        for script in ("pin.js", "background.js"):
            done = subprocess.run(["node", "--check", str(EXTENSION / script)],
                                  capture_output=True, text=True)
            check(f"{script} parses", done.returncode, 0)
    else:
        print("  --   node not installed, the extension's scripts were not parsed")

    print("which service asked")
    check("a service's own browser", host.app_from_cmdline([
        "/usr/lib64/chromium-browser/chromium-browser", "--app=https://www.youtube.com/tv",
        "--user-data-dir=/var/home/tv/.local/share/freetvos/webapps/youtube",
        "--class=freetvos-youtube"]), "youtube")
    check("not a settings page, whatever its window class says", host.app_from_cmdline([
        "chromium-browser", "--user-data-dir=/tmp/freetvos-ui-4411",
        "--class=freetvos-netflix"]), "")
    check("not an ordinary browser", host.app_from_cmdline([
        "chromium-browser", "--user-data-dir=/var/home/tv/.config/chromium"]), "")

    proc = tmp / "proc"
    for pid, ppid, name, args in (
            (900, 800, "python3", ["python3", "/usr/bin/freetvos-pin-host"]),
            # As Chromium leaves it after rewriting its process title: one
            # string, switches separated by spaces, user agent and all.
            (800, 1, "chromium (browser) x", [
                "/usr/lib64/chromium-browser/chromium-browser --app=https://www.netflix.com/browse "
                "--user-data-dir=/var/home/tv/.local/share/freetvos/webapps/netflix "
                "--class=freetvos-netflix --user-agent=Mozilla/5.0 (X11; Linux aarch64)"]),
            (700, 600, "python3", ["python3", "/usr/bin/freetvos-pin-host"]),
            (600, 1, "chromium", ["chromium-browser", "--user-data-dir=/tmp/elsewhere"])):
        (proc / str(pid)).mkdir(parents=True)
        (proc / str(pid) / "cmdline").write_bytes(b"\0".join(a.encode() for a in args) + b"\0")
        (proc / str(pid) / "stat").write_text(f"{pid} ({name}) S {ppid} 1 1 0 -1\n")
    check("found by walking up to the browser, through a name with brackets in it",
          host.calling_app(900), "netflix")
    check("and none when that browser is not a service", host.calling_app(700), "")

    print("addresses")
    title = f"{site}/title/80057281"
    check("where someone came from is not part of the page",
          host.normalise(f"{title}/?trackId=14170286&tctx=1%2C2"), host.normalise(title))
    check("which video is", host.normalise(f"{site}/watch?v=aaa") == host.normalise(f"{site}/watch?v=bbb"),
          False)
    for bad in ("javascript:alert(1)", "file:///etc/passwd", f"{site}/a b",
                f'{site}/"x', f"{site}/a\nExec=evil", ""):
        check(f"refused: {bad[:30]!r}", host.valid_link(bad), False)

    print("pinning through the helper")
    r = host.handle({"op": "status", "url": title}, "netflix")
    check("not pinned yet", (r["ok"], r["pinned"]), (True, False))
    r = host.handle({"op": "pin", "url": f"{title}?trackId=9", "name": "  Stranger\tThings ",
                     "image": ""}, "netflix")
    check("pinned", (r["ok"], r["pinned"], r["id"], r.get("name")),
          (True, True, "stranger-things", "Stranger Things"))
    entry = (desktop / "freetvos-pin-stranger-things.desktop").read_text()
    check("the tile opens the page through the service",
          [l for l in entry.splitlines() if l.startswith("Exec=")],
          [f'Exec=/usr/bin/freetvos-webapp netflix "{title}?trackId=9"'])
    check("with the poster the page advertised",
          sorted(p.name for p in (data / "freetvos/posters").iterdir()),
          ["freetvos-pin-stranger-things.png"])
    r = host.handle({"op": "status", "url": f"{title}/"}, "netflix")
    check("the same page spelled differently is already pinned", (r["pinned"], r["id"]),
          (True, "stranger-things"))
    r = host.handle({"op": "pin", "url": title, "name": "Stranger Things 4"}, "netflix")
    check("and pinning it again adds nothing", sorted(p.name for p in pins.iterdir()),
          ["stranger-things.pin"])
    r = host.handle({"op": "status", "url": title}, "youtube")
    check("a pin belongs to its service", r["pinned"], False)

    host.handle({"op": "pin", "url": f"{site}/watch?v=one", "name": "Chapter One"}, "youtube")
    host.handle({"op": "pin", "url": f"{site}/watch?v=two", "name": "Chapter One"}, "youtube")
    check("two episodes with one name are two pins",
          sorted(p.name for p in pins.iterdir()),
          ["chapter-one-2.pin", "chapter-one.pin", "stranger-things.pin"])

    r = host.handle({"op": "pin", "url": f"{site}/web/index.html", "name": "Films"},
                    "myjellyfin")
    check("a service added on the television can be pinned", (r["ok"], r["id"]),
          (True, "films"))

    r = host.handle({"op": "unpin", "url": f"{title}?tctx=0"}, "netflix")
    check("removed", (r["ok"], r["pinned"]), (True, False))
    check("and everything it made is gone",
          (desktop / "freetvos-pin-stranger-things.desktop").exists()
          or (pins / "stranger-things.pin").exists()
          or (data / "freetvos/posters/freetvos-pin-stranger-things.png").exists(), False)

    print("what the helper refuses")
    check("a browser that is not a service",
          host.handle({"op": "pin", "url": title, "name": "x"}, "")["ok"], False)
    check("a service that is not installed",
          host.handle({"op": "pin", "url": title, "name": "x"}, "hulu")["error"],
          "This service is no longer installed, so it cannot be pinned.")
    check("a page that is not a web address",
          host.handle({"op": "pin", "url": "javascript:alert(1)", "name": "x"}, "netflix")["ok"],
          False)
    check("a page with no name",
          host.handle({"op": "pin", "url": f"{site}/x", "name": " \n "}, "netflix")["error"],
          "This page has no name to pin it under.")
    check("something that is not a request", host.handle(["pin"], "netflix")["ok"], False)

    print("talking to Chromium")
    origin = host.EXTENSION_ORIGIN
    done = subprocess.run([sys.executable, str(HOST), origin],
                          input=frame({"op": "status", "url": title}), capture_output=True)
    check("one framed answer, and nothing that is not a service may pin",
          unframe(done.stdout), {"ok": False, "error":
                                 "Only a service opened from the home screen can be pinned."})
    done = subprocess.run([sys.executable, str(HOST), "chrome-extension://someoneelse/"],
                          input=frame({"op": "status", "url": title}), capture_output=True)
    check("another extension gets nothing at all", (done.returncode, done.stdout), (1, b""))
    done = subprocess.run([sys.executable, str(HOST), origin],
                          input=struct.pack("=I", 10**7), capture_output=True)
    check("an absurd length is refused rather than read", unframe(done.stdout)["ok"], False)

    print("freetvos-pin, with a name from a web page")
    hostile = "Evil $(touch PWNED) `touch PWNED2`"
    r = host.handle({"op": "pin", "url": f"{site}/evil", "name": hostile}, "netflix")
    check("pinned under exactly that name", r.get("name"), hostile)
    listing = pin_cli("list")
    check("listing it runs nothing", sorted(p.name for p in tmp.glob("PWNED*")), [])
    check("and shows the name as written", hostile in listing.stdout, True)
    entry = (desktop / f"freetvos-pin-{r['id']}.desktop").read_text()
    check("the desktop entry carries it as text", f"Name={hostile}" in entry, True)

    before = sorted(p.name for p in pins.iterdir())
    done = pin_cli("add", "--name", "Two\nExec=/usr/bin/evil", "--app", "netflix",
                   "--url", f"{site}/two")
    check("a name with a new line in it is refused", (done.returncode != 0,
          sorted(p.name for p in pins.iterdir())), (True, before))
    done = pin_cli("add", "--name", "Spaces", "--app", "netflix", "--url", f"{site}/a b")
    check("an address with a space in it is refused", done.returncode != 0, True)
    done = pin_cli("add", "--name", "Poster", "--app", "netflix", "--url", f"{site}/p",
                   "--image", "file:///etc/passwd")
    check("a poster that is not a web address is refused", done.returncode != 0, True)
    done = pin_cli("add", "--name", "Nope", "--app", "../../etc", "--url", f"{site}/n")
    check("an app that is not a name is refused", done.returncode != 0, True)
    done = pin_cli("remove", "../../../etc/passwd")
    check("so is removing something that is not a pin", done.returncode != 0, True)

    done = pin_cli("add", "--name", "Percent", "--app", "youtube",
                   "--url", f"{site}/search?q=50%25$off")
    entry = (desktop / "freetvos-pin-percent.desktop").read_text()
    check("% is doubled on the Exec line, and $ is sent encoded",
          [l for l in entry.splitlines() if l.startswith("Exec=")],
          [f'Exec=/usr/bin/freetvos-webapp youtube "{site}/search?q=50%%25%%24off"'])

    if failures:
        print(f"\n{len(failures)} failed")
        return 1
    print("\nall checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
