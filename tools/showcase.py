#!/usr/bin/env python3
"""Photograph the running television for the README, and record a short demo.

Drives the VM exactly as the other test tools do: surfaces are opened inside
the viewer's session with systemd-run, keys arrive through QEMU's monitor, and
frames come from the hypervisor's framebuffer. Nothing is staged in a browser on
the host, so every picture is what the television actually draws.

  python3 tools/showcase.py stills     one screenshot per feature
  python3 tools/showcase.py demo       a GIF of moving around the interface,
                                       ending on two services in split view

Needs the VM running (make run) and ffmpeg on the host. Output goes to
docs/images, scaled to 1280 wide: large enough to read, small enough that the
repository is not mostly pictures.

Nothing here signs into anything. A fresh disk has no accounts, and the stills
are chosen so that none of them depends on one.
"""
import json
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
IMAGES = REPO / "docs/images"
QMP = REPO / "output/qmp.sock"
WIDTH = 1280

# Opened one at a time, photographed, closed. The wait is how long each takes
# to draw on the VM, which is longer than on real hardware.
STILLS = [
    ("home", None, 0, "row-start"),
    ("setup", "/usr/bin/freetvos-setup run", 14, []),
    ("setup-keyboard", None, 0, "keyboard"),
    ("apps", "/usr/bin/freetvos-service browse", 14, []),
    ("scores", "/usr/bin/freetvos-sports browse", 18, []),
    ("scores-game", None, 0, ["ret"]),
    ("library", "/usr/bin/freetvos-media browse", 14, []),
    ("inputs", "/usr/bin/freetvos-hdmi show", 14, []),
    ("picture-sound", "/usr/bin/freetvos-tune show", 14, []),
    ("split-picker", "/usr/bin/freetvos-split pick", 16, []),
    ("tickers", "/usr/bin/freetvos-bars settings", 16, []),
    ("stock-picker", None, 0, ["down", "down", "down", "ret"]),
    ("livetv-guide", "/usr/bin/freetvos-livetv browse", 18, []),
    ("livetv-watching", None, 0, "watch"),
]


# A stand-in for nmcli inside the VM, answering only the three questions the
# wizard asks. The networks are made up; the page drawing them is not.
FAKE_NMCLI = r"""cat > /tmp/showcase-nmcli <<'EOF'
#!/bin/sh
case "$*" in
  *DEVICE,TYPE,STATE*) echo "wlan0:wifi:disconnected" ;;
  *CONNECTIVITY*) echo "none" ;;
  *IN-USE,SSID,SIGNAL,SECURITY*) printf '%s\n' " :Living Room:82:WPA2" \
      " :Upstairs:61:WPA2" " :Guest:44:" ;;
  *) exit 0 ;;
esac
EOF
chmod 755 /tmp/showcase-nmcli"""


def qmp(commands: list) -> None:
    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    s.connect(str(QMP))
    f = s.makefile("rw")

    def send(payload):
        f.write(json.dumps(payload) + "\n")
        f.flush()
        while True:
            message = json.loads(f.readline())
            if "event" not in message:
                return message

    json.loads(f.readline())
    send({"execute": "qmp_capabilities"})
    for payload in commands:
        send(payload)
    s.close()


def keys(*names: str, gap: float = 0.35) -> None:
    for name in names:
        qmp([{"execute": "send-key",
              "arguments": {"keys": [{"type": "qcode", "data": name}]}}])
        time.sleep(gap)


def grab(target: Path) -> None:
    """One frame, scaled for the page."""
    with tempfile.TemporaryDirectory() as tmp:
        raw = Path(tmp) / "frame.ppm"
        qmp([{"execute": "screendump", "arguments": {"filename": str(raw)}}])
        subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", str(raw),
                        "-vf", f"scale={WIDTH}:-2:flags=lanczos", str(target)],
                       check=True)


def vm(command: str) -> None:
    subprocess.run([str(REPO / "tools/vmssh.sh"), command], check=False,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def vm_ok(command: str) -> bool:
    return subprocess.run([str(REPO / "tools/vmssh.sh"), command],
                          stdout=subprocess.DEVNULL,
                          stderr=subprocess.DEVNULL).returncode == 0


def chord(*names: str) -> None:
    """Keys held together, such as the split view's next-pane shortcut."""
    qmp([{"execute": "send-key",
          "arguments": {"keys": [{"type": "qcode", "data": n} for n in names]}}])
    time.sleep(0.4)


def close_everything() -> None:
    """Back to the home screen, with nothing of ours left open."""
    # The bracket keeps each pattern from matching the command running it:
    # pkill -f searches whole command lines, and the shell carrying this one
    # over ssh contains the pattern too, so without it the cleanup kills its
    # own session before it has finished.
    vm("pkill -f '[c]lass=freetvos-' ; pkill -f '[f]reetvos-(setup|service|"
       "sports|media|hdmi|tune|split|pick|livetv|meet)' ; "
       "pkill -f '[f]reetvos-bars settings' ; pkill -f '[l]ivetv-ipc.sock' ; true")
    time.sleep(4)


def open_surface(command: str, wait: int, unit: str,
                 keep: bool = False) -> None:
    """Start something in the viewer's session.

    keep leaves alone whatever the command starts. A transient job stops every
    process it launched once its own command exits, and split view's command
    exits as soon as the panes are tiled, so the first recording filmed two
    browsers being killed a few seconds after they opened. A tile launched
    from the home screen gets its own scope and has no such problem.
    """
    kill = "-p KillMode=process " if keep else ""
    vm(f"systemd-run --user --machine=tv@ --quiet --collect --unit={unit} "
       f"{kill}{command}")
    time.sleep(wait)


def stills() -> int:
    IMAGES.mkdir(parents=True, exist_ok=True)
    close_everything()
    for n, (name, command, wait, extra) in enumerate(STILLS):
        if command:
            close_everything()
            open_surface(command, wait, f"showcase{n}")
        if extra == "row-start":
            # Back to the first tile, however far along the row the last
            # person left it. The start of the row is the first impression.
            keys(*["left"] * 25, gap=0.12)
            time.sleep(2)
        elif extra == "keyboard":
            # The VM is wired with no radio, so the network step has nothing
            # to select. The wizard takes its network tool from
            # FREETVOS_NMCLI, so it is shown a stand-in list of networks and
            # the page opens its keyboard on one of them, drawn by the device.
            close_everything()
            vm(FAKE_NMCLI)
            open_surface("/usr/bin/env FREETVOS_NMCLI=/tmp/showcase-nmcli "
                         "/usr/bin/freetvos-setup run", 14, f"showcase{n}")
            keys("ret")
            time.sleep(6)
            keys("down", "ret")
            time.sleep(2)
            keys("h", "o", "m", "e", gap=0.2)
            time.sleep(1)
        elif extra == "watch":
            # Enter tunes, then Up changes channel, and the picture is taken
            # while the channel banner is still on screen.
            keys("ret")
            time.sleep(14)
            keys("up")
            time.sleep(1.2)
        elif extra:
            keys(*extra)
            time.sleep(6)
        target = IMAGES / f"{name}.png"
        grab(target)
        print(f"  {target.relative_to(REPO)}")
    close_everything()
    return 0


def demo() -> int:
    """A walk around the interface, as a GIF."""
    IMAGES.mkdir(parents=True, exist_ok=True)
    close_everything()
    with tempfile.TemporaryDirectory() as tmp:
        frames = Path(tmp)
        count = 0
        filmed = 0.0

        def hold(seconds: float) -> None:
            nonlocal count, filmed
            start = time.time()
            end = start + seconds
            while time.time() < end:
                grab(frames / f"{count:04d}.png")
                count += 1
            filmed += time.time() - start

        keys(*["left"] * 25, gap=0.12)
        time.sleep(2)
        hold(2.0)                                   # the home screen
        keys("right", "right", "right", gap=0.5)
        hold(1.5)
        open_surface("/usr/bin/freetvos-sports browse", 16, "demo1")
        hold(2.5)                                   # live scores
        keys("right", "down", gap=0.6)
        hold(1.5)
        keys("ret")
        time.sleep(4)
        hold(2.5)                                   # one game
        close_everything()
        open_surface("/usr/bin/freetvos-service browse", 14, "demo2")
        hold(2.0)                                   # the app catalogue
        keys("right", "right", "down", gap=0.6)
        hold(1.5)
        close_everything()
        open_surface("/usr/bin/freetvos-hdmi show", 14, "demo3")
        hold(2.0)                                   # external inputs
        close_everything()

        # Split view from the tile: pick a service for each pane, open both.
        # The picker lists services alphabetically, six to a row, so YouTube
        # is one row down and four along, and ESPN+ is two along. Neither
        # needs an account to show something worth looking at.
        # Through the tile itself, the way pressing Split View does it.
        open_surface("/usr/bin/kioclient exec "
                     "/usr/share/applications/freetvos-split.desktop",
                     16, "demo4", keep=True)
        hold(1.5)                                   # choose the left pane
        keys("down", "right", "right", "right", "right", gap=0.45)
        hold(1.0)
        keys("ret")
        hold(1.0)                                   # choose the right pane
        keys("right", "right", gap=0.45)
        hold(1.0)
        keys("ret")
        hold(1.2)                                   # ready: Open is selected
        keys("ret")
        # Not filmed: two browsers starting from cold. Wait until both panes
        # exist, then give the pages time to draw before holding on them.
        both = ("test \"$(runuser -u tv -- env XDG_RUNTIME_DIR=/run/user/1000 "
                "/usr/bin/freetvos-split list | wc -l)\" -ge 2")
        deadline = time.time() + 90
        while time.time() < deadline and not vm_ok(both):
            time.sleep(3)
        time.sleep(18)
        hold(3.0)                                   # YouTube beside ESPN+
        chord("ctrl", "alt", "tab")
        hold(2.5)                                   # the highlight moves over
        close_everything()
        hold(1.5)

        target = IMAGES / "demo.gif"
        # Played back at the rate they were taken, so the GIF runs in real
        # time. Frames only arrive while holding on a screen, not during the
        # waits for a surface to open, so the rate comes from time spent
        # holding. A fixed rate guessed in advance made the first recording
        # run five times too slowly.
        rate = f"{max(1.0, count / max(filmed, 0.1)):.2f}"
        palette = frames / "palette.png"
        subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-framerate",
                        rate, "-i", str(frames / "%04d.png"), "-vf",
                        "scale=960:-2:flags=lanczos,palettegen=stats_mode=diff",
                        str(palette)], check=True)
        subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-framerate",
                        rate, "-i", str(frames / "%04d.png"), "-i",
                        str(palette), "-lavfi",
                        "scale=960:-2:flags=lanczos[x];[x][1:v]paletteuse="
                        "dither=bayer:bayer_scale=4", str(target)], check=True)
        print(f"  {target.relative_to(REPO)} from {count} frames "
              f"at {rate} per second")
    return 0


def main() -> int:
    if not QMP.exists():
        print("no VM: start it with make run", file=sys.stderr)
        return 1
    what = sys.argv[1] if len(sys.argv) > 1 else ""
    if what == "stills":
        return stills()
    if what == "demo":
        return demo()
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main())
