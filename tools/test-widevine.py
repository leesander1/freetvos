#!/usr/bin/env python3
"""Check that Widevine is taken out of Chrome's package whole and correct.

Chrome's package has three files called manifest.json. Taking the first by name
installed MEIPreload's beside the Widevine module, so Chromium was told nothing
about which formats it decrypts and YouTube TV said "This format is not
supported". This builds a package laid out the same way, decoy first, and
checks the right files come out and a wrong manifest is refused.

Run with: python3 tools/test-widevine.py
"""
import io
import json
import lzma
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
EXTRACT = REPO / "image/overlay/usr/share/freetvos/widevine/extract-deb.py"
INSTALL = REPO / "image/overlay/usr/bin/freetvos-widevine-install"
failures = []

WIDEVINE = {"name": "WidevineCdm", "version": "4.10.3112.0",
            "x-cdm-codecs": "vp8,vp09,avc1,av01", "x-cdm-interface-versions": "10"}
DECOY = {"name": "MEI Preload", "version": "1.0.7"}


def check(label, got, want):
    if got == want:
        print(f"  ok   {label}")
    else:
        print(f"  FAIL {label}\n         got  {got!r}\n         want {want!r}")
        failures.append(label)


def deb(path: Path) -> None:
    files = [  # in package order, decoys first
        ("./opt/google/chrome/MEIPreload/manifest.json", json.dumps(DECOY).encode()),
        ("./opt/google/chrome/PrivacySandboxAttestationsPreloaded/manifest.json", b"{}"),
        ("./opt/google/chrome/WidevineCdm/_platform_specific/linux_x64/._libwidevinecdm.so", b"stub"),
        ("./opt/google/chrome/WidevineCdm/_platform_specific/linux_x64/libwidevinecdm.so", b"\x7fELF" + b"x" * 4096),
        ("./opt/google/chrome/WidevineCdm/manifest.json", json.dumps(WIDEVINE).encode()),
    ]
    raw = io.BytesIO()
    with tarfile.open(fileobj=raw, mode="w") as tar:
        for name, data in files:
            info = tarfile.TarInfo(name)
            info.size = len(data)
            tar.addfile(info, io.BytesIO(data))
    members = [("debian-binary", b"2.0\n"), ("data.tar.xz", lzma.compress(raw.getvalue()))]
    out = bytearray(b"!<arch>\n")
    for name, data in members:
        out += f"{name + '/':<16}{0:<12}{0:<6}{0:<6}{100644:<8}{len(data):<10}`\n".encode()
        out += data + (b"\n" if len(data) % 2 else b"")
    path.write_bytes(bytes(out))


def extract(package, wanted, outdir):
    done = subprocess.run([sys.executable, str(EXTRACT), str(package), wanted, str(outdir)],
                          capture_output=True, text=True)
    return done.returncode


def manifest_ok(path) -> int:
    text = INSTALL.read_text()
    start = text.index("manifest_ok() {")
    end = text.index("\n}\n", start) + 3
    return subprocess.run(["bash", "-c", text[start:end] + '\nmanifest_ok "$1"', "_", str(path)]).returncode


def main() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        package = tmp / "chrome.deb"
        deb(package)
        out = tmp / "cdm"

        print("taking files out of the package")
        check("the manifest by path is Widevine's, not the first one",
              (extract(package, "WidevineCdm/manifest.json", out),
               json.loads((out / "manifest.json").read_text()).get("name")),
              (0, "WidevineCdm"))
        check("the module by path is the library, not the resource-fork stub",
              (extract(package, "WidevineCdm/_platform_specific/linux_x64/libwidevinecdm.so", out),
               (out / "libwidevinecdm.so").read_bytes()[:4]), (0, b"\x7fELF"))
        check("a path that is not there is an error", extract(package, "WidevineCdm/nope.json", out), 1)
        check("a partial name does not match a longer one",
              extract(package, "idevineCdm/manifest.json", out), 1)

        print("the installer's manifest check")
        good = tmp / "good.json"
        good.write_text(json.dumps(WIDEVINE))
        bad = tmp / "bad.json"
        bad.write_text(json.dumps(DECOY))
        check("Widevine's manifest passes", manifest_ok(good), 0)
        check("MEIPreload's is refused", manifest_ok(bad), 1)
        check("a missing one is refused", manifest_ok(tmp / "missing.json"), 1)

    print("wiring")
    text = INSTALL.read_text()
    check("the x86 path asks for both files by path",
          "WidevineCdm/manifest.json" in text
          and "WidevineCdm/_platform_specific/linux_x64/libwidevinecdm.so" in text, True)
    check("a present module with a wrong manifest is fetched again",
          'manifest_ok "$CDM_ROOT/manifest.json"' in text, True)
    units = REPO / "image/overlay/usr/lib/systemd/system"
    for name in ("freetvos-widevine-install.service", "freetvos-widevine-install.timer",
                 "freetvos-widevine-request.path"):
        check(f"{name} runs until the install is verified, not just present",
              "ConditionPathExists=!/var/lib/freetvos/widevine/.verified"
              in (units / name).read_text(), True)

    if failures:
        print(f"\n{len(failures)} failed")
        return 1
    print("\nall checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
