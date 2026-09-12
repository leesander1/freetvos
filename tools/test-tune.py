#!/usr/bin/env python3
"""Check picture, sound and Bluetooth against recorded tool output.

Every one of these settings is read by running a tool and reading what it says
back, so the part that can be wrong is the reading. The fixtures below are real
output captured from the television: kscreen-doctor's JSON, pactl's JSON, and
bluetoothctl's plain text, which is the awkward one.

Run with: python3 tools/test-tune.py
"""
import importlib.machinery
import importlib.util
import json
import sys
from pathlib import Path

sys.dont_write_bytecode = True

REPO = Path(__file__).resolve().parent.parent
SOURCE = REPO / "image/overlay/usr/bin/freetvos-tune"

failures = []


def check(label, got, want):
    if got == want:
        print(f"  ok   {label}")
    else:
        print(f"  FAIL {label}\n         got  {got!r}\n         want {want!r}")
        failures.append(label)


def load():
    loader = importlib.machinery.SourceFileLoader("freetvos_tune", str(SOURCE))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


KSCREEN = json.dumps({"outputs": [
    {"name": "HDMI-A-1", "connected": True, "enabled": True,
     "currentModeId": "1", "overscan": 4, "modes": [
         {"id": "1", "name": "1920x1080@60", "refreshRate": 59.97,
          "size": {"width": 1920, "height": 1080}},
         {"id": "4", "name": "3840x2160@60", "refreshRate": 60.0,
          "size": {"width": 3840, "height": 2160}},
         {"id": "13", "name": "1920x1080@50", "refreshRate": 50.0,
          "size": {"width": 1920, "height": 1080}},
         {"id": "bad", "name": "broken", "refreshRate": 0, "size": {}},
     ]},
    {"name": "HDMI-A-2", "connected": False, "modes": []},
]})

SINKS = json.dumps([
    {"index": 49, "name": "alsa_output.pci-0000_00_1f.3.hdmi-stereo",
     "description": "Television", "properties": {"device.bus": "pci"}},
    {"index": 50, "name": "bluez_output.AC_12_2F_00_11_22.1",
     "description": "WH-1000XM4", "properties": {}},
    {"index": 51, "name": "alsa_output.usb-Generic_USB_Audio.analog-stereo",
     "description": "USB Audio", "properties": {"device.bus": "usb"}},
])

BLUETOOTHCTL_DEVICES = """Device AC:12:2F:00:11:22 WH-1000XM4
Device 04:5D:4B:99:88:77 TV Remote
Device 11:22:33:44:55:66 Somebody's Phone
"""

INFO_CONNECTED = """Device AC:12:2F:00:11:22 (public)
\tName: WH-1000XM4
\tAlias: WH-1000XM4
\tPaired: yes
\tTrusted: yes
\tBlocked: no
\tConnected: yes
\tIcon: audio-headset
"""
INFO_PAIRED = """Device 04:5D:4B:99:88:77 (public)
\tName: TV Remote
\tPaired: yes
\tTrusted: yes
\tConnected: no
\tIcon: input-keyboard
"""
INFO_NEARBY = """Device 11:22:33:44:55:66 (public)
\tName: Somebody's Phone
\tPaired: no
\tTrusted: no
\tConnected: no
"""


def main() -> int:
    tune = load()

    calls = []

    def fake_run(argv, timeout=30):
        calls.append(argv)
        if argv[:2] == ["kscreen-doctor", "-j"]:
            return KSCREEN
        if argv[:4] == ["pactl", "-f", "json", "list"]:
            return SINKS
        if argv[:2] == ["pactl", "get-default-sink"]:
            return "bluez_output.AC_12_2F_00_11_22.1\n"
        if argv[:2] == ["wpctl", "get-volume"]:
            return "Volume: 0.45\n"
        if argv[:2] == ["bluetoothctl", "devices"]:
            return BLUETOOTHCTL_DEVICES

        if argv[:2] == ["bluetoothctl", "info"]:
            return {"AC:12:2F:00:11:22": INFO_CONNECTED,
                    "04:5D:4B:99:88:77": INFO_PAIRED,
                    "11:22:33:44:55:66": INFO_NEARBY}.get(argv[2], "")
        return ""

    tune.run = fake_run
    # An adapter is a directory in sysfs, which is how the code asks.
    tune.ADAPTERS = str(Path(__file__).resolve().parent.parent / ".git")
    real_listdir = __import__("os").listdir
    tune.os = type("os", (), {"listdir": staticmethod(lambda p: ["hci0"])})()

    print("the screen")
    screens = tune.displays()
    check("only what is connected", [s["name"] for s in screens], ["HDMI-A-1"])
    screen = screens[0]
    check("largest and smoothest first",
          [tune.mode_label(m) for m in screen["modes"]],
          ["3840x2160 at 60Hz", "1920x1080 at 59.97Hz", "1920x1080 at 50Hz"])
    check("a mode with no size is dropped",
          [m["id"] for m in screen["modes"]], ["4", "1", "13"])
    check("what is set now", screen["current"], "1")
    check("overscan is read", screen["overscan"], 4)

    print("where the sound goes")
    sinks = tune.outputs()
    check("all of them", [s["label"] for s in sinks],
          ["Television", "WH-1000XM4", "USB Audio"])
    check("the one in use is marked",
          [s["label"] for s in sinks if s["current"]], ["WH-1000XM4"])
    check("told apart by how they are attached",
          [s["kind"] for s in sinks], ["HDMI", "Bluetooth", "USB"])

    print("volume")
    check("read as a percentage", tune.volume(), 45)
    check("not muted", tune.muted(), False)

    print("things that are paired")
    devices = tune.devices()
    check("only paired ones by default",
          [d["name"] for d in devices], ["WH-1000XM4", "TV Remote"])
    check("connected first", devices[0]["connected"], True)
    check("the other is paired and idle",
          (devices[1]["paired"], devices[1]["connected"]), (True, False))
    everything = tune.devices(known_only=False)
    check("and everything when asked",
          sorted(d["name"] for d in everything),
          ["Somebody's Phone", "TV Remote", "WH-1000XM4"])
    check("an address is read exactly", devices[0]["address"],
          "AC:12:2F:00:11:22")

    print("with nothing attached")
    tune.run = lambda argv, timeout=30: ""
    check("no screen", tune.displays(), [])
    check("no outputs", tune.outputs(), [])
    tune.os = type("os", (), {"listdir": staticmethod(
        lambda p: (_ for _ in ()).throw(OSError()))})()
    check("no adapter", tune.bluetooth_ready(), False)
    check("and no devices are claimed", tune.devices(), [])
    check("volume falls back rather than throwing", tune.volume(), 0)

    print()
    if failures:
        print(f"{len(failures)} check(s) failed")
        return 1
    print("all checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
