#!/usr/bin/env python3
"""Check the setup wizard's network reading against recorded nmcli output.

nmcli's terse format is the awkward part: fields are separated by colons and a
colon inside a field is escaped, which network names contain more often than
you would expect. Everything below is that parsing, plus the rules about what
to show and in what order, none of which needs a radio.

Run with: python3 tools/test-setup.py
"""
import importlib.machinery
import importlib.util
import os
import sys
import tempfile
import time
import types
from pathlib import Path

sys.dont_write_bytecode = True

REPO = Path(__file__).resolve().parent.parent
SOURCE = REPO / "image/overlay/usr/bin/freetvos-setup"

failures = []


def check(label, got, want):
    if got == want:
        print(f"  ok   {label}")
    else:
        print(f"  FAIL {label}\n         got  {got!r}\n         want {want!r}")
        failures.append(label)


def load(root: Path):
    os.environ["XDG_STATE_HOME"] = str(root / "state")
    os.environ["FREETVOS_SETUP_STAMP"] = str(root / "state/setup-done")
    loader = importlib.machinery.SourceFileLoader("freetvos_setup", str(SOURCE))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


# Two radios for one network, an open one, one with a colon in its name, and a
# hidden one with no name at all.
WIFI_LIST = (
    "*:Home\\:Wifi:71:WPA2\n"
    " :Home\\:Wifi:48:WPA2\n"
    " :Neighbour:55:WPA1 WPA2\n"
    " :CoffeeShop:39:\n"
    " ::22:WPA2\n"
)
DEVICES = "enp0s1:ethernet:connected\nwlan0:wifi:disconnected\nlo:loopback:unmanaged\n"
CONNECTIONS = "Home\\:Wifi:802-11-wireless\nWired connection 1:802-3-ethernet\n"


def reply(code=0, out="", err=""):
    return types.SimpleNamespace(returncode=code, stdout=out, stderr=err)


def main() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        setup = load(Path(tmp))

        print("undoing the terse format")
        check("a plain line", setup._split("a:b:c"), ["a", "b", "c"])
        check("an escaped colon stays in its field",
              setup._split("Home\\:Wifi:71:WPA2"), ["Home:Wifi", "71", "WPA2"])
        check("an escaped backslash", setup._split("a\\\\b:c"), ["a\\b", "c"])
        check("empty fields survive", setup._split("::x"), ["", "", "x"])

        calls = []

        def fake(args, timeout=20):
            calls.append(args)
            if args[:2] == ["-t", "-f"] and args[2] == "CONNECTIVITY":
                return reply(out="full\n")
            if args[2] == "DEVICE,TYPE,STATE":
                return reply(out=DEVICES)
            if args[2] == "IN-USE,SSID,SIGNAL,SECURITY":
                return reply(out=WIFI_LIST)
            if args[2] == "ACTIVE,SSID":
                return reply(out="no:Neighbour\nyes:Home\\:Wifi\n")
            if args[2] == "NAME,TYPE":
                return reply(out=CONNECTIONS)
            return reply()

        setup._run = fake

        print("what is attached")
        check("online", setup.online(), True)
        check("the wifi adapter", setup.wifi_device(), "wlan0")
        check("a cable is plugged in", setup.wired_connected(), True)
        check("what it is joined to", setup.current_network(), "Home:Wifi")

        print("what is in range")
        found = setup.networks()
        check("one entry per name", [n["ssid"] for n in found],
              ["Home:Wifi", "Neighbour", "CoffeeShop"])
        check("the joined one first, then by strength",
              [n["signal"] for n in found], [71, 55, 39])
        check("the stronger radio of the two wins", found[0]["signal"], 71)
        check("open networks are known to be open",
              [n["secured"] for n in found], [True, True, False])
        check("a hidden network is not offered, having no name to show",
              any(n["ssid"] == "" for n in found), False)
        check("it asked for a fresh scan",
              any("--rescan" in c for c in calls), True)

        print("what is remembered")
        check("saved wireless connections", setup.saved_networks(),
              {"Home:Wifi"})

        print("joining")

        def joining(answer):
            """Joining looks the adapter up first, so that has to answer too."""
            def run(args, timeout=20):
                if len(args) > 2 and args[2] == "DEVICE,TYPE,STATE":
                    return reply(out=DEVICES)
                return answer
            return run

        setup._run = joining(reply())
        check("a network with no password", setup.connect("CoffeeShop"),
              (True, ""))
        setup._run = joining(reply(
            1, err="Error: Connection activation failed: Secrets were "
                   "required, but not provided."))
        joined, reason = setup.connect("Home:Wifi", "hunter2")
        check("a wrong password is named as one",
              (joined, reason), (False, "That password was not accepted."))
        setup._run = joining(reply(1, err="Error: Timeout 70 sec expired."))
        check("a timeout is named as one",
              setup.connect("Far Away", "x")[1],
              "The network did not answer in time.")
        setup._run = joining(None)
        check("nmcli not answering is not a crash",
              setup.connect("Anything"),
              (False, "The network manager did not answer."))

        print("what it was told to run")
        seen = []
        def watch(args, timeout=20):
            seen.append(args)
            if len(args) > 2 and args[2] == "DEVICE,TYPE,STATE":
                return reply(out=DEVICES)
            return reply()
        setup._run = watch
        setup.connect("My Net", "secret")
        joined_with = next(a for a in seen if a[:3] == ["device", "wifi", "connect"])
        check("the name is passed as one argument, not split on its space",
              joined_with[3], "My Net")
        check("on the wifi adapter", joined_with[4:6], ["ifname", "wlan0"])
        check("with the password", joined_with[6:8], ["password", "secret"])

        print("with no adapter")
        setup._run = lambda args, timeout=20: reply(out="lo:loopback:unmanaged\n")
        check("no wifi device", setup.wifi_device(), "")
        check("nothing in range", setup.networks(), [])
        check("and joining says so",
              setup.connect("Whatever")[1],
              "This television has no wifi adapter.")

        print("having been done")
        check("not yet", setup.done(), False)
        setup.mark_done()
        check("now", setup.done(), True)
        setup.mark_done()
        check("twice is fine", setup.done(), True)
        setup.reset()
        check("and it can be asked to run again", setup.done(), False)
        setup.reset()
        check("resetting twice is fine", setup.done(), False)

        print("game streaming")
        log = Path(tmp) / "moonlight.log"
        missing = Path(tmp) / "moonlight-missing"
        here = Path(tmp) / "moonlight-here"
        missing.write_text(f'#!/bin/sh\necho "$1" >> {log}\n'
                           '[ "$1" = status ] && echo "not installed"\nexit 0\n')
        here.write_text(f'#!/bin/sh\necho "$1" >> {log}\n'
                        '[ "$1" = status ] && echo "installed, version 6.1.0"\nexit 0\n')
        for stub in (missing, here):
            stub.chmod(0o755)

        setup.MOONLIGHT = str(missing)
        check("not there yet", setup.moonlight_installed(), False)
        setup.MOONLIGHT = str(here)
        check("there", setup.moonlight_installed(), True)

        setup.MOONLIGHT = str(missing)
        setup.moonlight_install()
        # Two gigabytes: it is started and left running, so the wizard can
        # carry on. Wait for the child rather than assume it has run yet.
        for _ in range(40):
            if log.exists() and "install" in log.read_text():
                break
            time.sleep(0.05)
        check("installing starts it without waiting for it",
              "install" in log.read_text(), True)
        setup.moonlight_remove()
        check("removing asks it to go", "remove" in log.read_text(), True)

        setup.MOONLIGHT = str(Path(tmp) / "not-installed-at-all")
        check("a command that is not there is not a crash",
              setup.moonlight_installed(), False)
        setup.moonlight_install()
        setup.moonlight_remove()
        check("and neither is asking it to do things", True, True)

    print()
    if failures:
        print(f"{len(failures)} check(s) failed")
        return 1
    print("all checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
