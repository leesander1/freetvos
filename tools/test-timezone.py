#!/usr/bin/env python3
"""Check the time zone set from the connection.

A stand-in timedatectl and a geoip answer from a file, so the parts that can go
wrong are checked without a network: an answer that is not a zone, a zone this
system has no rules for, and one chosen by hand being left alone.

Run with: python3 tools/test-timezone.py
"""
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

sys.dont_write_bytecode = True
REPO = Path(__file__).resolve().parent.parent
TOOL = REPO / "image/overlay/usr/bin/freetvos-timezone"
failures = []


def check(label, got, want):
    if got == want:
        print(f"  ok   {label}")
    else:
        print(f"  FAIL {label}\n         got  {got!r}\n         want {want!r}")
        failures.append(label)


def main() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        zones = tmp / "zoneinfo"
        for zone in ("America/Chicago", "Europe/London", "UTC"):
            (zones / zone).parent.mkdir(parents=True, exist_ok=True)
            (zones / zone).write_text("rules")
        state = tmp / "tz"
        state.write_text("UTC")
        fake = tmp / "timedatectl"
        fake.write_text(f"""#!/bin/sh
case "$1" in
  show) cat {state} ;;
  set-timezone) printf %s "$2" > {state} ;;
esac
""")
        fake.chmod(0o755)
        answer = tmp / "geoip.json"
        env = dict(os.environ, FREETVOS_GEOIP=answer.as_uri(),
                   FREETVOS_ZONEINFO=str(zones), FREETVOS_TIMEDATECTL=str(fake),
                   FREETVOS_TIMEZONE_CHOSEN=str(tmp / "chosen"))

        def run(*args):
            done = subprocess.run([sys.executable, str(TOOL), *args],
                                  capture_output=True, text=True, env=env)
            return done.returncode

        print("from the connection")
        answer.write_text(json.dumps({"time_zone": "America/Chicago", "city": "X"}))
        check("the looked-up zone is set", (run("auto"), state.read_text()),
              (0, "America/Chicago"))
        answer.write_text(json.dumps({"time_zone": "Mars/Olympus"}))
        check("a zone this system has no rules for is refused",
              (run("auto"), state.read_text()), (1, "America/Chicago"))
        answer.write_text(json.dumps({"time_zone": "../../etc/passwd"}))
        check("and so is anything that is not a zone name",
              (run("auto"), state.read_text()), (1, "America/Chicago"))
        answer.write_text("<html>")
        check("an answer that is not JSON changes nothing",
              (run("auto"), state.read_text()), (1, "America/Chicago"))

        print("chosen by hand")
        check("a chosen zone is set", (run("set", "Europe/London"), state.read_text()),
              (0, "Europe/London"))
        answer.write_text(json.dumps({"time_zone": "America/Chicago"}))
        check("and the lookup leaves it alone", (run("auto"), state.read_text()),
              (0, "Europe/London"))
        check("a made-up zone cannot be chosen", run("set", "Nowhere/Town"), 2)
        check("going back to automatic looks it up again",
              (run("automatic"), state.read_text()), (0, "America/Chicago"))

    print("wiring")
    hook = (REPO / "image/overlay/usr/lib/NetworkManager/dispatcher.d/"
            "90-freetvos-timezone").read_text()
    check("runs when a connection comes up, without holding it up",
          "up|connectivity-change)" in hook and "--no-block" in hook, True)
    containerfile = (REPO / "image/Containerfile").read_text()
    check("NetworkManager's dispatcher is enabled",
          "      NetworkManager-dispatcher \\" in containerfile, True)
    check("the hook is executable in the image",
          "/usr/lib/NetworkManager/dispatcher.d/90-freetvos-timezone" in containerfile, True)

    if failures:
        print(f"\n{len(failures)} failed")
        return 1
    print("\nall checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
