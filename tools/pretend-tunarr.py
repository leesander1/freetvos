"""A pretend Tunarr, for trying Live TV with no server on the network.

Three looping test channels and a guide written around the current time.

Serves the same paths Tunarr does, so the television is pointed at it exactly
as it would be at the real thing: /api/channels.m3u, /api/xmltv.xml,
/discover.json and /lineup.json. The guide is written around the current time
on every request, so there is always something on now and next.
"""
import datetime as dt
import http.server
import json
import sys
from pathlib import Path

import subprocess

HERE = Path(__file__).resolve().parent.parent / "output/pretend-tunarr"
# The address the television will use to reach this machine. From inside the
# QEMU VM, the Mac is always 10.0.2.2.
HOST = next((a for a in sys.argv[1:] if a.startswith("http")), "http://10.0.2.2:8951")


def make_channels() -> None:
    """Thirty seconds of each test channel, a picture pattern and a tone each.

    The pattern is how the channels are told apart on screen: the ffmpeg that
    ships with Homebrew cannot draw text, so there are no channel names burned
    in.
    """
    HERE.mkdir(parents=True, exist_ok=True)
    for name, source, tone in (("ch1.ts", "testsrc2", 440),
                               ("ch2.ts", "smptehdbars", 660),
                               ("ch3.ts", "mandelbrot", 880)):
        subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                        "-f", "lavfi", "-i", f"{source}=size=1280x720:rate=30",
                        "-f", "lavfi", "-i", f"sine=frequency={tone}", "-t", "30",
                        "-c:v", "libx264", "-preset", "veryfast",
                        "-pix_fmt", "yuv420p", "-c:a", "aac", "-f", "mpegts",
                        str(HERE / name)], check=True)
        print("made", HERE / name)
CHANNELS = [
    ("1", "C1.test", "Test Pattern One", "ch1.ts",
     ["Morning Shapes", "Colour Hour", "Late Lines", "Night Grid"]),
    ("2", "C2.test", "Bars and Tone", "ch2.ts",
     ["Calibration Live", "The Tone Show", "Bars After Dark", "Signal Off"]),
    ("7", "C7.test", "Fractal Channel", "ch3.ts",
     ["Deep Zoom", "Self Similar", "Infinite Coast", "Edge of Chaos"]),
]


def m3u() -> str:
    lines = [f'#EXTM3U url-tvg="{HOST}/api/xmltv.xml" x-tvg-url="{HOST}/api/xmltv.xml"']
    for number, cid, name, stream, _ in CHANNELS:
        lines.append(f'#EXTINF:-1 tvg-id="{cid}" channel-id="{cid}" tvg-chno="{number}" '
                     f'tvg-name="{name}" group-title="Test",{name}')
        lines.append(f"{HOST}/stream/{stream}")
    return "\n".join(lines) + "\n"


def xmltv() -> str:
    fmt = "%Y%m%d%H%M%S +0000"
    now = dt.datetime.now(dt.timezone.utc).replace(second=0, microsecond=0)
    start = now.replace(minute=0) - dt.timedelta(minutes=30)
    out = ['<?xml version="1.0" encoding="UTF-8"?>', '<tv generator-info-name="pretend-tunarr">']
    for number, cid, name, _, _ in CHANNELS:
        out.append(f'  <channel id="{cid}"><display-name>{number} {name}</display-name>'
                   f'<display-name>{number}</display-name><display-name>{name}</display-name></channel>')
    for index, (number, cid, name, _, shows) in enumerate(CHANNELS):
        length = [30, 60, 45][index]
        t = start
        i = 0
        while t < now + dt.timedelta(hours=6):
            stop = t + dt.timedelta(minutes=length)
            title = shows[i % len(shows)]
            out.append(f'  <programme start="{t.strftime(fmt)}" stop="{stop.strftime(fmt)}" channel="{cid}">'
                       f'<title lang="en">{title}</title><desc lang="en">{title} on {name}.</desc></programme>')
            t, i = stop, i + 1
    out.append("</tv>")
    return "\n".join(out) + "\n"


class Handler(http.server.BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def send(self, body: bytes, kind: str):
        self.send_response(200)
        self.send_header("Content-Type", kind)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = self.path.split("?")[0]
        if path == "/api/channels.m3u":
            return self.send(m3u().encode(), "audio/x-mpegurl")
        if path == "/api/xmltv.xml":
            return self.send(xmltv().encode(), "application/xml")
        if path == "/discover.json":
            return self.send(json.dumps({"FriendlyName": "Pretend Tunarr", "DeviceID": "TEST0001",
                                         "TunerCount": 2, "BaseURL": HOST,
                                         "LineupURL": f"{HOST}/lineup.json"}).encode(), "application/json")
        if path == "/lineup.json":
            return self.send(json.dumps([{"GuideNumber": n, "GuideName": name, "URL": f"{HOST}/stream/{s}"}
                                         for n, _, name, s, _ in CHANNELS]).encode(), "application/json")
        if path.startswith("/stream/"):
            f = HERE / Path(path).name
            if f.suffix == ".ts" and f.exists():
                return self.send(f.read_bytes(), "video/mp2t")
        self.send_response(404)
        self.end_headers()


if __name__ == "__main__":
    if "--make-channels" in sys.argv[1:] or not (HERE / "ch1.ts").exists():
        make_channels()
    print(f"pretend Tunarr at {HOST}")
    http.server.ThreadingHTTPServer(("0.0.0.0", 8951), Handler).serve_forever()
