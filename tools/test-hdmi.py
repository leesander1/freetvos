#!/usr/bin/env python3
"""Check the external-input logic without a capture device attached.

The parts most likely to be wrong here are the ones hardest to check on the
television: which /dev/video node is the picture and which is a metadata stream,
which sound card belongs to which dongle, and which of the dozens of formats a
device advertises is the one worth asking for. All three are decided from sysfs
and from text, so all three can be checked against a synthetic tree on any
machine.

Run with: python3 tools/test-hdmi.py
"""
import importlib.machinery
import importlib.util
import os
import sys

# Loading commands out of the overlay tree would otherwise leave __pycache__
# directories in it, which the image build then copies into /usr.
sys.dont_write_bytecode = True
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SOURCE = REPO / "image/overlay/usr/bin/freetvos-hdmi"

failures = []


def check(label, got, want):
    if got == want:
        print(f"  ok   {label}")
    else:
        print(f"  FAIL {label}\n         got  {got!r}\n         want {want!r}")
        failures.append(label)


def load(root: Path):
    """Load the command with its view of the world pointed at a fake tree."""
    os.environ["FREETVOS_HDMI_SYSFS"] = str(root / "sys")
    os.environ["FREETVOS_HDMI_DEV"] = str(root / "dev")
    os.environ["FREETVOS_HDMI_CONFD"] = str(root / "conf")
    os.environ["XDG_CONFIG_HOME"] = str(root / "xdg")
    # The command has no .py suffix, so the loader has to be named outright
    # rather than inferred from the extension.
    loader = importlib.machinery.SourceFileLoader("freetvos_hdmi", str(SOURCE))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


# ---------------------------------------------------------------------------
# A USB tree with one capture dongle and one webcam on it.
# ---------------------------------------------------------------------------

def build_tree(root: Path) -> None:
    sysfs = root / "sys"
    devices = sysfs / "devices/pci0000:00/usb1"

    def usb_device(bus, vid, pid, serial, product, maker, interfaces):
        base = devices / bus
        base.mkdir(parents=True, exist_ok=True)
        (base / "idVendor").write_text(vid + "\n")
        (base / "idProduct").write_text(pid + "\n")
        if serial:
            (base / "serial").write_text(serial + "\n")
        (base / "product").write_text(product + "\n")
        (base / "manufacturer").write_text(maker + "\n")
        for interface, kind, payload in interfaces:
            idir = base / f"{bus}:{interface}"
            if kind == "video":
                for node, index, name in payload:
                    ndir = idir / "video4linux" / node
                    ndir.mkdir(parents=True, exist_ok=True)
                    (ndir / "name").write_text(name + "\n")
                    (ndir / "index").write_text(str(index) + "\n")
                    # Real sysfs points a node at the USB interface that owns
                    # it, two levels up from the node directory.
                    os.symlink("../..", ndir / "device")
                    link = sysfs / "class/video4linux" / node
                    link.parent.mkdir(parents=True, exist_ok=True)
                    os.symlink(ndir, link)
            else:
                cdir = idir / "sound" / f"card{payload}"
                cdir.mkdir(parents=True, exist_ok=True)
                link = sysfs / "class/sound" / f"card{payload}"
                link.parent.mkdir(parents=True, exist_ok=True)
                os.symlink(cdir, link)
                (cdir / "id").write_text(f"Card{payload}\n")

    # The ten-dollar dongle: no serial number, sound on a second interface.
    usb_device("1-1", "534d", "2109", "", "USB3. 0", "MACROSILICON",
               [("1.0", "video", [("video0", 0, "USB3. 0: USB3. 0"),
                                  ("video1", 1, "USB3. 0: USB3. 0")]),
                ("1.2", "sound", 1)])
    # A webcam, which must not end up being offered as HDMI 1.
    usb_device("1-2", "04f2", "b6dd", "0001", "Integrated Camera", "Chicony",
               [("1.0", "video", [("video2", 0, "Integrated Camera")])])


MS2109_FORMATS = """ioctl: VIDIOC_ENUM_FMT
	Type: Video Capture

	[0]: 'MJPG' (Motion-JPEG, compressed)
		Size: Discrete 1920x1080
			Interval: Discrete 0.033s (30.000 fps)
			Interval: Discrete 0.040s (25.000 fps)
		Size: Discrete 1280x720
			Interval: Discrete 0.017s (60.000 fps)
	[1]: 'YUYV' (YUYV 4:2:2)
		Size: Discrete 1920x1080
			Interval: Discrete 0.200s (5.000 fps)
		Size: Discrete 1280x720
			Interval: Discrete 0.100s (10.000 fps)
"""

# The kernel's own test driver is a capture device and an output device at
# once, and so are some capture cards. Taking every format block would have the
# television offering to display a node that only accepts pictures.
BOTH_WAYS_FORMATS = """ioctl: VIDIOC_ENUM_FMT
	Type: Video Capture

	[0]: 'YUYV' (YUYV 4:2:2)
		Size: Discrete 1280x720
			Interval: Discrete 0.033s (30.000 fps)

	Type: Video Output

	[0]: 'RGB3' (24-bit RGB 8-8-8)
		Size: Discrete 3840x2160
			Interval: Discrete 0.017s (60.000 fps)
"""

OUTPUT_ONLY_FORMATS = """ioctl: VIDIOC_ENUM_FMT
	Type: Video Output

	[0]: 'RGB3' (24-bit RGB 8-8-8)
		Size: Discrete 1920x1080
			Interval: Discrete 0.017s (60.000 fps)
"""

# A dongle that claims more than it should. The cap exists for exactly this.
UHD_FORMATS = """ioctl: VIDIOC_ENUM_FMT
	Type: Video Capture

	[0]: 'MJPG' (Motion-JPEG, compressed)
		Size: Discrete 3840x2160
			Interval: Discrete 0.033s (30.000 fps)
		Size: Discrete 1920x1080
			Interval: Discrete 0.017s (60.000 fps)
"""

STEPWISE_FORMATS = """	[0]: 'NV12' (Y/UV 4:2:0)
		Size: Stepwise 32x32 - 3840x2160 with step 2/2
			Interval: Continuous 0.016s - 1.000s (60.000-1.000 fps)
"""


def main() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        build_tree(root)
        hdmi = load(root)

        print("format parsing")
        modes = hdmi._parse_formats(MS2109_FORMATS)
        check("modes found", len(modes), 5)
        check("first mode", modes[0],
              {"fourcc": "MJPG", "w": 1920, "h": 1080, "fps": 30.0})
        check("second rate on the same size", modes[1],
              {"fourcc": "MJPG", "w": 1920, "h": 1080, "fps": 25.0})
        check("raw format still listed", modes[3],
              {"fourcc": "YUYV", "w": 1920, "h": 1080, "fps": 5.0})
        check("stepwise maximum", hdmi._parse_formats(STEPWISE_FORMATS),
              [{"fourcc": "NV12", "w": 3840, "h": 2160, "fps": 60.0}])
        check("the output half is ignored",
              hdmi._parse_formats(BOTH_WAYS_FORMATS),
              [{"fourcc": "YUYV", "w": 1280, "h": 720, "fps": 30.0}])
        check("an output-only node is not a capture device",
              hdmi._parse_formats(OUTPUT_ONLY_FORMATS), [])

        print("choosing a mode")
        # The trap this exists to catch: raw and compressed both offer 1080p,
        # but only one of them can actually carry it over USB 2.
        check("rate beats encoding at the same size",
              hdmi.best_mode(modes, 1080),
              {"fourcc": "MJPG", "w": 1920, "h": 1080, "fps": 30.0})
        check("capped to 720p", hdmi.best_mode(modes, 720),
              {"fourcc": "MJPG", "w": 1280, "h": 720, "fps": 60.0})
        check("nothing usable", hdmi.best_mode([], 1080), None)
        check("label", hdmi.mode_label(modes[0]), "1920x1080 30Hz MJPG")
        check("round trip", hdmi.parse_mode_spec(hdmi.mode_spec(modes[0])),
              {"w": 1920, "h": 1080, "fps": 30.0, "fourcc": "MJPG"})

        print("telling capture devices from cameras")
        check("known vendor", hdmi.classify("USB3. 0", "USB3. 0",
                                            "MACROSILICON", "534d"), "hdmi")
        check("camera wins over its vendor",
              hdmi.classify("Elgato Facecam", "Facecam", "Elgato", "0fd9"),
              "camera")
        check("integrated camera",
              hdmi.classify("Integrated Camera", "Integrated Camera",
                            "Chicony", "04f2"), "camera")
        check("named by function",
              hdmi.classify("HDMI Capture", "", "", "1234"), "hdmi")
        check("no idea", hdmi.classify("Acme Thing", "", "", "1234"), "unknown")

        print("walking sysfs")
        # Every node the kernel offers, so the metadata node is in play.
        hdmi._modes = lambda node: (
            hdmi._parse_formats(MS2109_FORMATS)
            if node.endswith(("video0", "video2")) else [])
        found = {d["node"]: d for d in hdmi.devices()}
        check("metadata node dropped", sorted(found), ["video0", "video2"])
        check("dongle vendor", found["video0"]["vid"], "534d")
        check("sound paired by topology", found["video0"]["card"], 1)
        check("webcam has no sound", found["video2"]["card"], -1)
        check("dongle key", found["video0"]["key"], "534d-2109-1-1")
        check("webcam key uses its serial", found["video2"]["key"],
              "04f2-b6dd-0001")
        check("kinds", [found["video0"]["kind"], found["video2"]["kind"]],
              ["hdmi", "camera"])

        print("what the source list shows")
        items = {i["key"]: i for i in hdmi.inputs()}
        check("dongle is an input", items["534d-2109-1-1"]["role"], "input")
        check("dongle is numbered", items["534d-2109-1-1"]["label"], "HDMI 1")
        check("webcam is not offered", items["04f2-b6dd-0001"]["role"],
              "ignore")

        print("what is shown is what will be opened")
        # The tile used to advertise the best mode the hardware could name
        # while the viewer opened a capped one, so the label and the picture
        # disagreed on a 4K-claiming dongle.
        big = {"cfg": {"MODE": "auto"}, "modes": hdmi._parse_formats(UHD_FORMATS)}
        check("automatic obeys the cap", hdmi.chosen_mode(big),
              {"fourcc": "MJPG", "w": 1920, "h": 1080, "fps": 60.0})
        hdmi.write_conf(Path(os.environ["XDG_CONFIG_HOME"]) / "freetvos/hdmi.conf",
                        {"MAX_HEIGHT": "2160"})
        check("raising the cap raises the mode", hdmi.chosen_mode(big),
              {"fourcc": "MJPG", "w": 3840, "h": 2160, "fps": 30.0})
        check("an explicit choice overrides both",
              hdmi.chosen_mode({"cfg": {"MODE": "1280x720@50/MJPG"},
                                "modes": big["modes"]}),
              {"w": 1280, "h": 720, "fps": 50.0, "fourcc": "MJPG"})
        hdmi.write_conf(Path(os.environ["XDG_CONFIG_HOME"]) / "freetvos/hdmi.conf",
                        {"MAX_HEIGHT": "1080"})

        print("settings override the guess")
        conf = Path(os.environ["FREETVOS_HDMI_CONFD"])
        hdmi.write_conf(conf / "04f2-b6dd-0001.conf",
                        {"ROLE": "input", "NAME": "Doorbell"})
        hdmi.write_conf(conf / "534d-2109-1-1.conf",
                        {"NAME": "PlayStation", "MODE": "1280x720@60/MJPG",
                         "ASPECT": "16:9"})
        items = {i["key"]: i for i in hdmi.inputs()}
        check("promoted device", items["04f2-b6dd-0001"]["role"], "input")
        check("its chosen name", items["04f2-b6dd-0001"]["label"], "Doorbell")
        check("renamed dongle", items["534d-2109-1-1"]["label"], "PlayStation")

        print("what the viewer is told")
        argv = hdmi.viewer_argv(items["534d-2109-1-1"])
        check("device", argv[argv.index("--device") + 1],
              str(root / "dev/video0"))
        check("name", argv[argv.index("--name") + 1], "PlayStation")
        check("chosen size", argv[argv.index("--size") + 1], "1280x720")
        check("ffmpeg format name",
              argv[argv.index("--input-format") + 1], "mjpeg")
        check("rate", argv[argv.index("--fps") + 1], "60")
        check("its own sound card", argv[argv.index("--audio-card") + 1], "1")
        check("aspect", argv[argv.index("--aspect") + 1], "16:9")

        print("a device with two picture nodes")
        # Some cards present two capture streams; the keys have to stay apart
        # or the settings for one silently become the settings for both.
        hdmi._modes = lambda node: (
            hdmi._parse_formats(MS2109_FORMATS)
            if node.endswith(("video0", "video1")) else [])
        keys = sorted(d["key"] for d in hdmi.devices()
                      if d["vid"] == "534d")
        check("distinct keys", keys, ["534d-2109-1-1-n0", "534d-2109-1-1-n1"])

        print("the settings page and what it writes")
        # The pages share their machinery with every other surface, so the
        # parent directory comes along too.
        sys.path.insert(0, str(REPO / "image/overlay/usr/share/freetvos"))
        sys.path.insert(0, str(REPO / "image/overlay/usr/share/freetvos/hdmi"))
        import ui
        rows = ui.settings_model(hdmi)
        fields = [r for r in rows if r["kind"] == "field"]
        check("every field has options",
              all(len(r["options"]) >= 1 for r in fields), True)
        check("every value is one of its options",
              [r["key"] for r in fields
               if r["value"] not in [o[0] for o in r["options"]]], [])
        check("global rows are not attached to a device",
              [r["key"] for r in fields if not r["dev"]],
              ["ON_CONNECT", "AUDIO_LATENCY_MS", "MAX_HEIGHT",
               "AUTO_OPEN_SINGLE"])
        check("ends with the save row", rows[-1]["kind"], "action")

        ui.apply_values(hdmi, [
            {"dev": "534d-2109-1-1", "key": "NAME", "value": "Nintendo"},
            {"dev": "534d-2109-1-1", "key": "ASPECT", "value": "4:3"},
            {"dev": "", "key": "ON_CONNECT", "value": "switch"},
            {"dev": "", "key": "AUDIO_LATENCY_MS", "value": "80"},
        ])
        check("device setting saved",
              hdmi.read_conf(conf / "534d-2109-1-1.conf")["NAME"], "Nintendo")
        # The one that was already there and not touched by this save.
        check("untouched setting survives",
              hdmi.read_conf(conf / "534d-2109-1-1.conf")["MODE"],
              "1280x720@60/MJPG")
        check("global setting saved", hdmi.config()["ON_CONNECT"], "switch")
        check("connect options are the two that work",
              [o[0] for o in ui.ON_CONNECT], ["switch", "ignore"])
        check("default still applies where nothing was set",
              hdmi.config()["MAX_HEIGHT"], "1080")
        items = {i["key"]: i for i in hdmi.inputs()}
        check("the list reflects the save",
              items["534d-2109-1-1"]["label"], "Nintendo")

        print("a device that is remembered but unplugged")
        for link in (root / "sys/class/video4linux").iterdir():
            link.unlink()
        remembered = hdmi.inputs()
        check("still listed", sorted(i["key"] for i in remembered),
              ["04f2-b6dd-0001", "534d-2109-1-1"])
        check("marked absent", [i["present"] for i in remembered], [False, False])
        check("settings page copes", 
              any(r.get("sub") == "Remembered, but not plugged in"
                  for r in ui.settings_model(hdmi)), True)

        print("a machine with nothing plugged in")
        empty = Path(tempfile.mkdtemp())
        (empty / "sys/class/video4linux").mkdir(parents=True)
        (empty / "sys/class/sound").mkdir(parents=True)
        bare = load(empty)
        check("no devices", bare.devices(), [])
        check("no inputs", bare.inputs(), [])

    print()
    if failures:
        print(f"{len(failures)} check(s) failed")
        return 1
    print("all checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
