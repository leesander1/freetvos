#!/usr/bin/env python3
"""Check joining Zoom, Meet and Teams calls by ID, offline.

The part worth pinning down is turning what an invitation says, read aloud and
typed with a remote, into the address the browser needs: digits with spaces in
them, a Meet code in capitals without its hyphens, a pasted Zoom link that
points at a desktop app this box does not have. And refusing a link to anywhere
else, because this browser profile has the camera switched on.

Run with: python3 tools/test-meet.py
"""
import importlib.machinery
import importlib.util
import os
import sys
import tempfile
from pathlib import Path

sys.dont_write_bytecode = True

REPO = Path(__file__).resolve().parent.parent
SOURCE = Path(os.environ.get("FREETVOS_MEET_CMD_PATH",
                             REPO / "image/overlay/usr/bin/freetvos-meet"))

failures = []


def check(label, got, want):
    if got == want:
        print(f"  ok   {label}")
    else:
        print(f"  FAIL {label}\n         got  {got!r}\n         want {want!r}")
        failures.append(label)


def refused(label, fn):
    try:
        fn()
        check(label, "accepted", "refused")
    except ValueError:
        check(label, "refused", "refused")


def main() -> int:
    loader = importlib.machinery.SourceFileLoader("freetvos_meet", str(SOURCE))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    meet = importlib.util.module_from_spec(spec)
    loader.exec_module(meet)
    join = meet.join_url

    print("Zoom")
    check("an ID read aloud with spaces",
          join("zoom", "812 3456 7890"), "https://app.zoom.us/wc/join/81234567890")
    check("with its passcode", join("zoom", "812-3456-7890", "Ab1 2"),
          "https://app.zoom.us/wc/join/81234567890?pwd=Ab1%202")
    refused("too short to be a meeting", lambda: join("zoom", "1234"))

    print("Google Meet")
    check("a code as written", join("meet", "abc-defg-hij"),
          "https://meet.google.com/abc-defg-hij")
    check("in capitals, without hyphens", join("meet", "ABC DEFG HIJ"),
          "https://meet.google.com/abc-defg-hij")
    refused("nine letters is not a code", lambda: join("meet", "abcdefghi"))

    print("Microsoft Teams")
    check("an ID and passcode", join("teams", "123 456 789 012", "x7Y9"),
          "https://teams.microsoft.com/meet/123456789012?p=x7Y9")
    refused("an ID without its passcode", lambda: join("teams", "123456789012"))
    refused("an unknown service", lambda: join("skype", "123"))

    print("pasted invitation links")
    check("a Zoom desktop link becomes the browser client",
          meet.from_invite("https://us02web.zoom.us/j/81234567890?pwd=secret"),
          ("zoom", "https://app.zoom.us/wc/join/81234567890?pwd=secret"))
    check("a Meet link as it is",
          meet.from_invite("meet.google.com/abc-defg-hij"),
          ("meet", "https://meet.google.com/abc-defg-hij"))
    check("a Teams link as it is",
          meet.from_invite("https://teams.live.com/meet/9876543210?p=abc"),
          ("teams", "https://teams.live.com/meet/9876543210?p=abc"))
    check("an http link is upgraded",
          meet.from_invite("http://meet.google.com/abc-defg-hij")[1],
          "https://meet.google.com/abc-defg-hij")
    refused("a lookalike host is refused",
            lambda: meet.from_invite("https://zoom.us.evil.example/j/81234567890"))
    refused("anything else is refused",
            lambda: meet.from_invite("https://example.com/meeting"))
    refused("a Zoom link with no meeting in it",
            lambda: meet.from_invite("https://zoom.us/pricing"))

    print("telling a camera from a capture dongle")
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        for node, index, name in (("video0", "0", "Integrated Camera"),
                                  ("video1", "1", "Integrated Camera"),
                                  ("video2", "0", "USB3. 0 capture"),
                                  ("video3", "0", "Logitech BRIO")):
            d = root / "class/video4linux" / node
            d.mkdir(parents=True)
            (d / "name").write_text(name + "\n")
            (d / "index").write_text(index + "\n")
        meet.SYS = root
        check("cameras only, each once",
              meet.cameras(), ["Integrated Camera", "Logitech BRIO"])

    print()
    if failures:
        print(f"{len(failures)} check(s) failed")
        return 1
    print("all checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
