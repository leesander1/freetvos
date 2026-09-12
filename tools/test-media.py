#!/usr/bin/env python3
"""Check the library logic without a drive, a server or a network.

What is worth pinning down here is the translation: a folder on a disc, a Plex
episode and a Jellyfin episode are three different shapes that all have to come
out as one, and every one of them then has to turn back into a command line the
player understands. Everything below is that translation, which needs no
hardware to check.

Run with: python3 tools/test-media.py
"""
import importlib.machinery
import importlib.util
import json
import os
import sys
import tempfile
import time
from pathlib import Path

sys.dont_write_bytecode = True

REPO = Path(__file__).resolve().parent.parent
SHARED = REPO / "image/overlay/usr/share/freetvos"
SOURCE = REPO / "image/overlay/usr/bin/freetvos-media"

failures = []


def check(label, got, want):
    if got == want:
        print(f"  ok   {label}")
    else:
        print(f"  FAIL {label}\n         got  {got!r}\n         want {want!r}")
        failures.append(label)


def load(root: Path):
    os.environ.update(
        FREETVOS_USB_ROOT=str(root / "usb"),
        FREETVOS_MEDIA_CONF=str(root / "conf"),
        XDG_STATE_HOME=str(root / "state"),
        XDG_CONFIG_HOME=str(root / "conf"),
        XDG_DATA_HOME=str(root / "data"))
    sys.path.insert(0, str(SHARED))
    sys.path.insert(0, str(SHARED / "media"))
    loader = importlib.machinery.SourceFileLoader("freetvos_media", str(SOURCE))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


PLEX_EPISODE = {
    "ratingKey": "4821", "type": "episode", "title": "The Constant",
    "grandparentTitle": "Lost", "parentIndex": 4, "index": 5,
    "duration": 2640000, "viewOffset": 900000, "thumb": "/library/x/thumb",
    "Media": [{"Part": [{"key": "/library/parts/99/file.mkv"}]}],
}
PLEX_MOVIE = {
    "ratingKey": "12", "type": "movie", "title": "Arrival", "year": 2016,
    "duration": 6960000, "Media": [{"Part": [{"key": "/library/parts/3/a.mkv"}]}],
}
PLEX_SHOW = {"ratingKey": "700", "type": "show", "title": "Lost"}

JELLYFIN_EPISODE = {
    "Id": "abc", "Type": "Episode", "Name": "The Constant",
    "SeriesName": "Lost", "ParentIndexNumber": 4, "IndexNumber": 5,
    "RunTimeTicks": 26400000000, "ImageTags": {"Primary": "t"},
    "UserData": {"PlaybackPositionTicks": 9000000000},
}


def main() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        drive = root / "usb/MOVIES_2TB"
        (drive / "Films").mkdir(parents=True)
        (drive / ".Trashes").mkdir(parents=True)
        (drive / "System Volume Information").mkdir(parents=True)
        for name in ("Arrival.mkv", "notes.txt", "The Sting.mp4",
                     "soundtrack.flac"):
            (drive / "Films" / name).touch()
        media = load(root)

        print("looking at a drive")
        drives = media.usb_drives()
        check("one drive found", [d["name"] for d in drives], ["MOVIES 2TB"])
        check("its path", drives[0]["path"], str(drive))

        listing = media.list_folder(str(drive))
        check("rubbish is not shown", [e["title"] for e in listing], ["Films"])
        films = media.list_folder(str(drive / "Films"))
        # Sorted the way a person reads a list, so capitals do not come first.
        check("only what can be played, in a human order",
              [e["title"] for e in films],
              ["Arrival", "soundtrack", "The Sting"])
        check("all playable", {e["playable"] for e in films}, {True})
        check("a missing folder is empty, not a crash",
              media.list_folder(str(root / "nowhere")), [])

        print("what was left part way through")
        later = root / "state/freetvos/watch-later"
        later.mkdir(parents=True)
        (later / "one").write_text(
            f"# {drive}/Films/Arrival.mkv\nstart=1830.5\n")
        (later / "two").write_text(
            f"# {drive}/Films/The Sting.mp4\nstart=42\n")
        (later / "gone").write_text(f"# {drive}/Films/Deleted.mkv\nstart=10\n")
        # mpv writes one of these for every directory above what was played.
        # The path inside is a real directory, so only the marker rules it out.
        (later / "redirect").write_text(
            f"# redirect entry\n# {drive}/Films\n")
        # Opened and closed again without watching anything.
        (later / "zero").write_text(
            f"# {drive}/Films/Koyaanisqatsi.mkv\nstart=0.000000\n")
        os.utime(later / "two", (time.time(), time.time()))
        resume = media.local_resume()
        check("only what still exists, and was actually watched",
              sorted(r["title"] for r in resume), ["Arrival", "The Sting"])
        check("newest first", resume[0]["title"], "The Sting")
        check("position is read",
              [r["offset"] for r in resume if r["title"] == "Arrival"], [1830])

        print("one shape for three sources")
        episode = media.plex.normalise(PLEX_EPISODE)
        check("plex episode is named in full", episode["title"],
              "Lost · S4E5 · The Constant")
        check("plex position is seconds", episode["offset"], 900)
        check("plex duration is seconds", episode["duration"], 2640)
        check("plex file", episode["part"], "/library/parts/99/file.mkv")
        check("plex episode can be played", episode["playable"], True)
        check("a plex show cannot",
              media.plex.normalise(PLEX_SHOW)["playable"], False)
        check("a plex film can",
              media.plex.normalise(PLEX_MOVIE)["playable"], True)

        jf = media.jellyfin.normalise(JELLYFIN_EPISODE)
        check("jellyfin episode is named the same way", jf["title"],
              episode["title"])
        check("jellyfin position is seconds", jf["offset"], 900)
        check("jellyfin duration is seconds", jf["duration"], 2640)

        print("addresses")
        check("bare host gets a scheme and a port",
              media.jellyfin.normalise_address("jellyfin.local"),
              "http://jellyfin.local:8096")
        check("a port given is kept",
              media.jellyfin.normalise_address("10.0.0.5:9000"),
              "http://10.0.0.5:9000")
        check("https is left alone",
              media.jellyfin.normalise_address("https://jf.example.com/"),
              "https://jf.example.com")
        check("nothing is nothing", media.jellyfin.normalise_address(""), "")

        print("streaming")
        check("plex file carries the token",
              media.plex.stream_url("http://s:32400", "TOK",
                                    "/library/parts/1/f.mkv"),
              "http://s:32400/library/parts/1/f.mkv?X-Plex-Token=TOK")
        check("a part that already has a query keeps it",
              media.plex.stream_url("http://s:32400", "TOK", "/p?download=0"),
              "http://s:32400/p?download=0&X-Plex-Token=TOK")
        check("jellyfin streams the file itself",
              media.jellyfin.stream_url("http://jf:8096/", "TOK", "xyz"),
              "http://jf:8096/Videos/xyz/stream?static=true&api_key=TOK")

        print("turning a choice into a command")
        argv = media.play_target({"source": "local",
                                  "path": "/run/media/x/Film.mkv",
                                  "title": "Film"})
        check("local plays the file", argv[1], "/run/media/x/Film.mkv")
        check("and carries its name", argv[argv.index("--title") + 1], "Film")
        check("with no forced position", "--start" in argv, False)

        media._write("plex", {"token": "ACCOUNT",
                              "server": {"base": "http://s:32400",
                                         "token": "SRV", "name": "Home"}})
        argv = media.play_target({"source": "plex", "part": "/p/1.mkv",
                                  "title": "Arrival", "offset": 1830})
        check("plex plays through the server",
              argv[1], "http://s:32400/p/1.mkv?X-Plex-Token=SRV")
        check("the server's position wins",
              argv[argv.index("--start") + 1], "1830")

        media._write("jellyfin", {"base": "http://jf:8096", "token": "JT",
                                  "user": "u1", "name": "Home"})
        argv = media.play_target({"source": "jellyfin", "id": "xyz",
                                  "title": "Lost", "offset": 0})
        check("jellyfin plays through the server",
              argv[1],
              "http://jf:8096/Videos/xyz/stream?static=true&api_key=JT")
        check("no position means none is forced", "--start" in argv, False)

        print("what the library offers")
        found = {s["kind"] for s in media.sources()}
        check("a drive and two servers", sorted(found),
              ["jellyfin", "plex", "usb"])

        print("identity")
        first = media.client_id()
        check("looks like an identifier", len(first), 36)
        check("and does not change", media.client_id(), first)
        check("stored privately",
              oct((Path(os.environ["FREETVOS_MEDIA_CONF"])
                   / "device.json").stat().st_mode & 0o777), "0o600")

        print("forgetting")
        check("plex is forgotten", media.forget("plex"), True)
        check("and stays forgotten", media.forget("plex"), False)
        check("the other one is untouched",
              media.jellyfin_account().get("token"), "JT")

    print()
    if failures:
        print(f"{len(failures)} check(s) failed")
        return 1
    print("all checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
