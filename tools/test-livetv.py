#!/usr/bin/env python3
"""Check the Live TV reading against Tunarr-shaped replies, offline.

The fixtures mirror what Tunarr's own source writes: its M3U attributes, its
XMLTV display names, and its HDHomeRun discover and lineup replies. The awkward
parts are the ones pinned down here: a channel name with a comma in it, a guide
written in a time zone other than UTC, a lineup with no guide ids at all, and
channel numbers that sort the way a remote counts rather than the way text does.

Run with: python3 tools/test-livetv.py
"""
import datetime as dt
import json
import os
import sys
from pathlib import Path

sys.dont_write_bytecode = True

REPO = Path(__file__).resolve().parent.parent
FIXTURES = REPO / "tools/fixtures"
sys.path.insert(0, os.environ.get(
    "FREETVOS_LIVETV_PATH", str(REPO / "image/overlay/usr/share/freetvos/livetv")))

import guide                                                # noqa: E402

failures = []


def check(label, got, want):
    if got == want:
        print(f"  ok   {label}")
    else:
        print(f"  FAIL {label}\n         got  {got!r}\n         want {want!r}")
        failures.append(label)


UTC = dt.timezone.utc


def main() -> int:
    print("a Tunarr playlist")
    playlist = guide.parse_m3u((FIXTURES / "tunarr-channels.m3u").read_text())
    check("the guide address from the header", playlist["guide"],
          "http://tunarr.lan:8000/api/xmltv.xml")
    check("every channel", len(playlist["channels"]), 3)
    first = playlist["channels"][0]
    check("number, name and guide id",
          (first["number"], first["name"], first["guide_id"]),
          ("1", "Saturday Cartoons", "C1.tunarr.com"))
    check("a name with a comma stays whole",
          playlist["channels"][1]["name"], "Movie Night, Classics")
    check("the stream address", first["url"].endswith("streamMode=hls"), True)
    check("a channel with no logo has none", playlist["channels"][2]["logo"], "")
    try:
        guide.parse_m3u("<html>not a playlist")
        check("a web page is refused", "accepted", "refused")
    except guide.GuideError:
        check("a web page is refused", "refused", "refused")

    print("a Tunarr guide")
    xml = guide.parse_xmltv((FIXTURES / "tunarr-xmltv.xml").read_bytes())
    check("every channel's names",
          xml["channels"]["C2.tunarr.com"],
          ["2 Movie Night, Classics", "2", "Movie Night, Classics"])
    cartoons = xml["programmes"]["C1.tunarr.com"]
    check("shows in order", [s["title"] for s in cartoons],
          ["Space Rangers", "Robot Pals"])
    check("episode detail", (cartoons[0]["subtitle"], cartoons[0]["episode"]),
          ("The Comet", "S01E04"))
    check("entities in descriptions", cartoons[0]["description"],
          "The rangers chase a comet & lose their map.")
    sitcom = xml["programmes"]["C10.tunarr.com"][0]
    check("a guide written in New York time is not read as UTC",
          sitcom["start"].astimezone(UTC).hour, 0)
    check("a programme for a channel nobody listed is kept aside",
          "C99.missing" in xml["programmes"], True)
    check("times with no offset are UTC",
          guide.parse_xmltv_time("20260915180000").utcoffset(),
          dt.timedelta(0))
    check("a nonsense time is none", guide.parse_xmltv_time("soon"), None)

    print("what is on")
    now = dt.datetime(2026, 9, 15, 18, 10, tzinfo=UTC)
    current, upcoming = guide.on_now(cartoons, now)
    check("now", current["title"], "Space Rangers")
    check("next", upcoming["title"], "Robot Pals")
    early = dt.datetime(2026, 9, 15, 12, 0, tzinfo=UTC)
    check("before anything starts, only next",
          [s and s["title"] for s in guide.on_now(cartoons, early)],
          [None, "Space Rangers"])
    late = dt.datetime(2026, 9, 16, 12, 0, tzinfo=UTC)
    check("after everything, nothing", guide.on_now(cartoons, late),
          (None, None))
    check("at the exact end, the next show is on",
          guide.on_now(cartoons, dt.datetime(2026, 9, 15, 18, 30,
                                              tzinfo=UTC))[0]["title"],
          "Robot Pals")
    check("a window for the grid",
          [s["title"] for s in guide.window(
              cartoons, dt.datetime(2026, 9, 15, 18, 20, tzinfo=UTC),
              dt.datetime(2026, 9, 15, 18, 40, tzinfo=UTC))],
          ["Space Rangers", "Robot Pals"])

    print("matching channels to the guide")
    matched = guide.match_guide(playlist["channels"], xml)
    check("by the playlist's own ids", matched,
          {0: "C1.tunarr.com", 1: "C2.tunarr.com", 2: "C10.tunarr.com"})
    lineup = guide.parse_lineup(
        json.loads((FIXTURES / "hdhr-lineup.json").read_text()))
    check("a lineup has no guide ids", {c["guide_id"] for c in lineup}, {""})
    check("so it is matched by number and name",
          guide.match_guide(lineup, xml),
          {0: "C1.tunarr.com", 1: "C2.tunarr.com", 2: "C10.tunarr.com"})
    check("a channel the guide does not know is simply unmatched",
          guide.match_guide([{"number": "55", "name": "Mystery"}], xml), {})

    print("an HDHomeRun lineup")
    check("numbers and names", [(c["number"], c["name"]) for c in lineup],
          [("1", "Saturday Cartoons"), ("2", "Movie Night, Classics"),
           ("10", "Sitcoms")])
    check("an entry with no stream is dropped",
          guide.parse_lineup([{"GuideNumber": "3", "GuideName": "Off air"}]),
          [])

    print("addresses and order")
    norm = guide.normalise_address
    check("a bare name gets Tunarr's port", norm("tunarr.lan"),
          "http://tunarr.lan:8000")
    check("a port given is kept", norm("10.0.0.5:8089"), "http://10.0.0.5:8089")
    check("a full playlist address is left alone",
          norm("http://tv.lan/api/channels.m3u"), "http://tv.lan/api/channels.m3u")
    check("a tuner's default port is 80",
          guide.normalise_address("hdhr.lan", default_port=80),
          "http://hdhr.lan:80")
    check("nothing is nothing", norm(""), "")
    ordered = guide.sort_channels([{"number": "10", "name": "c"},
                                   {"number": "2", "name": "b"},
                                   {"number": "5.1", "name": "sub"},
                                   {"number": "5", "name": "a"},
                                   {"number": "", "name": "no number"}])
    check("2 before 10, 5 before 5.1, no number last",
          [c["number"] for c in ordered], ["2", "5", "5.1", "10", ""])

    print("the command: sources, merging, caching, where to start")
    import importlib.machinery
    import importlib.util
    import tempfile
    import time
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        os.environ["FREETVOS_LIVETV_CONF"] = str(root / "livetv.json")
        os.environ["FREETVOS_LIVETV_CACHE"] = str(root / "cache")
        command = Path(os.environ.get(
            "FREETVOS_LIVETV_CMD_PATH",
            REPO / "image/overlay/usr/bin/freetvos-livetv"))
        loader = importlib.machinery.SourceFileLoader("freetvos_livetv",
                                                      str(command))
        spec = importlib.util.spec_from_loader(loader.name, loader)
        livetv = importlib.util.module_from_spec(spec)
        loader.exec_module(livetv)

        check("a Tunarr address becomes its playlist and guide",
              livetv.tunarr_source("tunarr.lan"),
              {"kind": "m3u", "label": "Tunarr at http://tunarr.lan:8000",
               "playlist": "http://tunarr.lan:8000/api/channels.m3u",
               "guide": "http://tunarr.lan:8000/api/xmltv.xml"})

        # Local files stand in for the server: the reader fetches file://
        # addresses the same way it fetches http:// ones.
        playlist = (FIXTURES / "tunarr-channels.m3u").as_uri()
        xmltv = (FIXTURES / "tunarr-xmltv.xml").as_uri()
        livetv.add_source({"kind": "m3u", "label": "fixture",
                           "playlist": playlist, "guide": xmltv})
        livetv.add_source({"kind": "m3u", "label": "fixture",
                           "playlist": playlist, "guide": xmltv})
        check("adding the same source twice keeps one",
              len(livetv.settings()["sources"]), 1)

        at = dt.datetime(2026, 9, 15, 18, 10, tzinfo=UTC)
        result = livetv.lineup(force=True, now=at)
        check("channels, sorted", [c["number"] for c in result["channels"]],
              ["1", "2", "10"])
        check("with tonight's guide attached",
              [s["title"] for s in result["channels"][0]["shows"]],
              ["Space Rangers", "Robot Pals"])
        check("no errors", result["errors"], [])

        cached = livetv.lineup(now=at)
        check("asked again soon, answered from the cache with real times",
              isinstance(cached["channels"][0]["shows"][0]["start"], dt.datetime),
              True)

        livetv.settings()
        data = livetv.settings()
        data["sources"][0]["playlist"] = (root / "gone.m3u").as_uri()
        livetv.save(data)
        stale = livetv.lineup(force=True, now=at)
        check("a server that went away leaves the last channel list",
              [c["number"] for c in stale["channels"]], ["1", "2", "10"])
        check("and says so", any("last channel list" in e for e in stale["errors"]),
              True)

        channels = result["channels"]
        check("with nothing remembered, the first channel",
              livetv.start_index(channels), 0)
        livetv.remember_last(channels[2])
        check("otherwise the last one watched", livetv.start_index(channels), 2)
        check("a number asked for wins", livetv.start_index(channels, "2"), 1)
        check("a number that does not exist falls back to the last",
              livetv.start_index(channels, "99"), 2)

        livetv.remove_source(0)
        check("a source can be removed", livetv.settings()["sources"], [])

    print()
    if failures:
        print(f"{len(failures)} check(s) failed")
        return 1
    print("all checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
