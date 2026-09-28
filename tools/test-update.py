#!/usr/bin/env python3
"""Check automatic updates: the switch, reading bootc, and when to restart.

The parts that can be wrong without a television to hand: what counts as
switched off, which systems can update at all, whether an update is really
waiting, whether something is playing, and the night window. Plus the wiring:
that the image masks bootc's own restart-whenever timer and that installs are
pointed at the published image.

Run with: python3 tools/test-update.py
"""
import datetime as dt
import importlib.machinery
import importlib.util
import json
import os
import sys
import tempfile
from pathlib import Path

sys.dont_write_bytecode = True

REPO = Path(__file__).resolve().parent.parent
SOURCE = REPO / "image/overlay/usr/bin/freetvos-update"
UI = REPO / "image/overlay/usr/share/freetvos"

failures = []


def check(label, got, want):
    if got == want:
        print(f"  ok   {label}")
    else:
        print(f"  FAIL {label}\n         got  {got!r}\n         want {want!r}")
        failures.append(label)


def load():
    loader = importlib.machinery.SourceFileLoader("freetvos_update", str(SOURCE))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


def host(spec_image="ghcr.io/leesander1/freetvos:latest", transport="registry",
         booted="sha256:aaa", staged=None):
    def deployment(digest, stamp):
        return {"image": {"image": {"image": spec_image, "transport": transport},
                          "version": "0.1.0", "timestamp": stamp,
                          "imageDigest": digest}}
    return {
        "apiVersion": "org.containers.bootc/v1", "kind": "BootcHost",
        "spec": {"image": {"image": spec_image, "transport": transport}},
        "status": {
            "booted": deployment(booted, "2026-09-28T10:00:00Z"),
            "staged": deployment(staged, "2026-09-29T10:00:00Z") if staged else None,
            "rollback": None,
        },
    }


PACTL_PLAYING = """Sink Input #52
\tDriver: protocol-native.c
\tSink: 48
\tCorked: no
\tMute: no
\tproperties:
\t\tapplication.name = "Chromium"
"""
PACTL_PAUSED = PACTL_PLAYING.replace("Corked: no", "Corked: yes")


def main() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        os.environ["FREETVOS_UPDATE_CONFIG"] = str(Path(tmp) / "config")
        os.environ["FREETVOS_UPDATE_STATUS"] = str(Path(tmp) / "status.json")
        up = load()

        print("the switch")
        check("on when never set", up.enabled(), True)
        up.set_enabled(False)
        check("off once switched off", up.enabled(), False)
        check("kept in the account's own settings",
              json.loads((Path(tmp) / "config/updates.json").read_text()),
              {"automatic": False})
        up.set_enabled(True)
        check("and on again", up.enabled(), True)
        (Path(tmp) / "config/updates.json").write_text("{not json")
        check("a broken file leaves updates on", up.enabled(), True)
        (Path(tmp) / "config/updates.json").write_text('{"automatic": "no"}')
        check("only false switches them off", up.enabled(), True)

        print("Check now")
        check("nothing pending at first", up.check_pending(), False)
        up.request_check()
        check("asking leaves the file the path unit watches",
              (Path(tmp) / "config/update-request").exists(), True)
        check("and counts as pending", up.check_pending(), True)

        print("reading bootc")
        check("a published image can update",
              up.tracking(host()), "ghcr.io/leesander1/freetvos:latest")
        check("a local image cannot",
              up.tracking(host(spec_image="localhost/freetvos:latest")), "")
        check("nor the copy on the USB stick",
              up.tracking(host(spec_image="/run/install/repo/container",
                               transport="oci")), "")
        s = up.summarise(host(staged="sha256:bbb"))
        check("a different staged image is an update waiting",
              (s["staged"] or {}).get("digest"), "sha256:bbb")
        check("the running one is described",
              (s["booted"]["version"], s["booted"]["built"]),
              ("0.1.0", "2026-09-28T10:00:00Z"))
        check("the same image staged again is not",
              up.summarise(host(staged="sha256:aaa"))["staged"], None)
        check("nothing staged is nothing waiting", up.summarise(host())["staged"], None)

        print("check first, then download")
        h = host()
        check("nothing found is nothing waiting", up.waiting_update(h), None)
        h["status"]["booted"]["cachedUpdate"] = {"image": {"image": "x"},
                                                 "imageDigest": "sha256:ccc",
                                                 "timestamp": "2026-09-29T01:00:00Z"}
        check("a newer image found is waiting", (up.waiting_update(h) or {}).get("digest"),
              "sha256:ccc")
        h["status"]["booted"]["cachedUpdate"]["imageDigest"] = "sha256:aaa"
        check("the running image is not new", up.waiting_update(h), None)
        staged = host(staged="sha256:ccc")
        staged["status"]["booted"]["cachedUpdate"] = {"imageDigest": "sha256:ccc"}
        check("nor the one already downloaded", up.waiting_update(staged), None)
        check("the last line of output", up.last_line("a\n\n  b  \n"), "b")

        def broken():
            raise KeyError("imageDigest")
        state = up.safely(broken)
        check("a step that breaks is written down as a failed check",
              (state["checking"], state["result"], state["error"]),
              (False, "error", "KeyError: 'imageDigest'"))

        # A stand-in bootc: status from a file, --check finds a new image, and
        # the download prints progress and stages it.
        fake = Path(tmp) / "bin"
        fake.mkdir()
        (fake / "bootc").write_text(f"""#!/usr/bin/env python3
import json, sys, time
from pathlib import Path
state = Path({str(Path(tmp) / "host.json")!r})
h = json.loads(state.read_text())
args = sys.argv[1:]
if args[:1] == ["status"]:
    print(json.dumps(h))
elif args == ["upgrade", "--check"]:
    h["status"]["booted"]["cachedUpdate"] = {{"image": {{"image": "x"}},
        "imageDigest": "sha256:new", "timestamp": "2026-09-29T01:00:00Z"}}
    state.write_text(json.dumps(h)); print("Update available")
elif args == ["upgrade"]:
    for n in (1, 2, 3):
        print(f"Fetching layer {{n}}/3", flush=True)
    h["status"]["staged"] = {{"image": {{"image": {{"image": "x"}},
        "imageDigest": "sha256:new", "timestamp": "2026-09-29T01:00:00Z"}}}}
    state.write_text(json.dumps(h))
""")
        (fake / "bootc").chmod(0o755)
        (Path(tmp) / "host.json").write_text(json.dumps(host()))
        os.environ["PATH"] = f"{fake}:{os.environ['PATH']}"
        state = up.download()
        check("a found update is downloaded and waits",
              (state["result"], (state.get("staged") or {}).get("digest"), state["checking"]),
              ("downloaded", "sha256:new", False))
        check("the page was told it was downloading, with bootc's progress",
              (state.get("phase"), state.get("detail")), ("", "Fetching layer 3/3"))
        state = up.download()
        check("asking again finds nothing more", state["result"], "downloaded")

        print("restarting")
        check("a sounding stream is playing", up.sink_inputs_playing(PACTL_PLAYING), True)
        check("a paused one is not", up.sink_inputs_playing(PACTL_PAUSED), False)
        check("no streams is not", up.sink_inputs_playing(""), False)
        day = dt.date(2026, 9, 28)
        at = lambda h, m: dt.datetime.combine(day, dt.time(h, m))
        check("1:59 is too early", up.in_window(at(1, 59)), False)
        check("2:00 may restart", up.in_window(at(2, 0)), True)
        check("5:29 may restart", up.in_window(at(5, 29)), True)
        check("5:30 is too late", up.in_window(at(5, 30)), False)
        check("the afternoon is too late", up.in_window(at(15, 0)), False)

        print("what the page says")
        local = dt.datetime(2026, 9, 28, 3, 12).astimezone()
        check("today", up.when(local.isoformat(), today=day), "today at 3:12 am")
        check("yesterday",
              up.when((local - dt.timedelta(days=1)).isoformat(), today=day),
              "yesterday at 3:12 am")
        check("longer ago",
              up.when(dt.datetime(2026, 9, 4, 15, 0).astimezone().isoformat(), today=day),
              "4 September")
        check("nonsense says nothing", up.when("soon"), "")
        check("up to date", up.status_line({"result": "current"}), "Up to date")
        check("checking", up.status_line({"checking": True}), "Checking for an update…")
        check("downloading says so, and that it is big the first time",
              up.status_line({"checking": True, "phase": "downloading"}).startswith(
                  "Downloading the new version") and "a few GB" in
              up.status_line({"checking": True, "phase": "downloading"}), True)
        check("an update waiting says how it finishes",
              up.status_line({"staged": {"built": ""}, "result": "downloaded"}),
              "An update is ready. It finishes when the TV restarts.")
        check("a system that cannot update says so",
              up.status_line({"result": "unmanaged"}).startswith(
                  "This TV is not set up to receive updates"), True)
        check("a failed check says why",
              up.status_line({"result": "error", "error": "no network"}).endswith(
                  ": no network"), True)
        check("the version", up.version_line({"booted": {"version": "0.1.0"}}),
              "Version 0.1.0")

        print("the page")
        sys.path.insert(0, str(UI))
        import updateui

        def rows_for(status):
            Path(os.environ["FREETVOS_UPDATE_STATUS"]).write_text(json.dumps(status))
            try:
                (Path(tmp) / "config/update-request").unlink()
            except OSError:
                pass
            return updateui.model(up)

        labels = [r.get("label") for r in rows_for({"result": "current"})]
        check("a switch, then Check now",
              ("Update automatically" in labels, "Check for an update now" in labels,
               "Restart now to finish the update" in labels), (True, True, False))
        labels = [r.get("label") for r in rows_for({"staged": {"digest": "b"}})]
        check("Restart now only when an update waits",
              "Restart now to finish the update" in labels, True)
        labels = [r.get("label") for r in rows_for({"checking": True})]
        check("no Check now while checking", "Check for an update now" in labels, False)
        labels = [r.get("label") for r in rows_for({"checking": True, "phase": "downloading",
                                                    "detail": "Fetching layer 2/9"})]
        check("bootc's progress is shown while downloading", "Fetching layer 2/9" in labels, True)
        up.set_enabled(False)
        field = next(r for r in rows_for({}) if r["kind"] == "field")
        check("the switch shows what is saved", field["value"], "off")

    print("the image and the installer")
    containerfile = (REPO / "image/Containerfile").read_text()
    check("bootc's restart-whenever timer is masked",
          "systemctl mask bootc-fetch-apply-updates.timer" in containerfile, True)
    check("FreeTVOS's timer, Check now and the version record are enabled",
          "systemctl enable freetvos-update.timer freetvos-update-check.path" in containerfile
          and "freetvos-update-status.service" in containerfile, True)
    check("the command is executable", "/usr/bin/freetvos-update " in containerfile, True)
    units = REPO / "image/overlay/usr/lib/systemd/system"
    check("Check now watches the file the page leaves",
          "PathExists=/var/home/tv/.config/freetvos/update-request"
          in (units / "freetvos-update-check.path").read_text(), True)
    for unit in units.glob("freetvos-update*"):
        check(f"{unit.name} leaves /var/lib/freetvos to the TV account",
              "StateDirectory=" in unit.read_text(), False)
    check("DIAL, which runs as that account, still keeps its state there",
          "StateDirectory=freetvos" in (units / "freetvos-dial.service").read_text()
          and "User=tv" in (units / "freetvos-dial.service").read_text(), True)

    print("Widevine on request")
    launcher = (REPO / "webapps/freetvos-webapp").read_text()
    check("opening a service without it asks for it",
          'REQUEST="${XDG_CONFIG_HOME:-$HOME/.config}/freetvos/widevine-request"' in launcher,
          True)
    check("the request is watched where the launcher leaves it",
          "PathExists=/var/home/tv/.config/freetvos/widevine-request"
          in (units / "freetvos-widevine-request.path").read_text(), True)
    request = (units / "freetvos-widevine-request.service").read_text()
    check("and cleared before the download starts, so it fires once",
          request.index("rm -f") < request.index("systemctl start"), True)
    check("the watch is enabled with the timer",
          "freetvos-widevine-request.path" in containerfile, True)
    check("offline, the message says to join a network",
          "Join a network in Setup" in launcher, True)
    workflow = (REPO / ".github/workflows/installer.yml").read_text()
    check("installs follow the published image",
          "bootc switch --mutate-in-place --transport registry ${UPDATE_IMAGE}" in workflow,
          True)
    check("the build publishes it", 'docker://${DEST}:${tag}' in workflow
          and "packages: write" in workflow, True)
    check("rechunked, before the installer is made or anything is published",
          workflow.index("Rechunk for small updates")
          < workflow.index("Build the installer ISO")
          < workflow.index("Publish the image for updates"), True)
    check("keeping the published image's layer plan, or none if it cannot be read",
          'rechunk --previous-build="$PREV" || rechunk' in workflow, True)
    check("and never with Widevine in it",
          workflow.index("Leave Widevine out") < workflow.index("Publish the image"), True)
    tile = (REPO / "image/overlay/usr/share/applications/freetvos-updates.desktop").read_text()
    check("the tile opens the page", "Exec=/usr/bin/freetvos-update show" in tile, True)
    check("and has its icon", (REPO / "brand/icons/freetvos-updates.svg").is_file(), True)

    if failures:
        print(f"\n{len(failures)} failed")
        return 1
    print("\nall checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
