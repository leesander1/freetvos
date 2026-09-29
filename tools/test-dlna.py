#!/usr/bin/env python3
"""Check the DLNA renderer the way a sender uses it, over HTTP and SOAP.

A real server on a spare port, with mpv replaced by a stand-in that remembers
what it was told, so the protocol is checked without a screen: the device and
service descriptions parse, each action answers, state moves as a sender
expects, seeking and volume reach the player, and a subscriber is sent events.

Run with: python3 tools/test-dlna.py
"""
import http.server
import importlib.machinery
import importlib.util
import os
import socket
import sys
import tempfile
import threading
import time
import urllib.request
from pathlib import Path
from xml.etree import ElementTree

sys.dont_write_bytecode = True
REPO = Path(__file__).resolve().parent.parent
failures = []


def check(label, got, want):
    if got == want:
        print(f"  ok   {label}")
    else:
        print(f"  FAIL {label}\n         got  {got!r}\n         want {want!r}")
        failures.append(label)


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class FakePlayer:
    def __init__(self):
        self.calls, self.volume, self.muted, self.alive = [], 100, False, False
        self.props = {"time-pos": 83.4, "duration": 3725.0}

    def running(self):
        return self.alive

    def start(self, uri, position=0.0):
        self.calls.append(("start", uri, position))
        self.alive = True

    def stop(self):
        if self.alive:
            self.calls.append(("stop",))
        self.alive = False

    def command(self, *args):
        self.calls.append(("command",) + args)

    def get(self, name):
        return self.props.get(name)

    def set(self, name, value):
        self.calls.append(("set", name, value))

    def set_volume(self, v):
        self.volume = v

    def set_mute(self, m):
        self.muted = m


def main() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        os.environ["STATE_DIRECTORY"] = tmp
        os.environ["FREETVOS_DLNA_PORT"] = str(free_port())
        loader = importlib.machinery.SourceFileLoader(
            "freetvos_dlna", str(REPO / "cast/dlna/freetvos-dlna.py"))
        spec = importlib.util.spec_from_loader(loader.name, loader)
        dlna = importlib.util.module_from_spec(spec)
        loader.exec_module(dlna)

        player = FakePlayer()
        renderer = dlna.Renderer(player)
        subs = dlna.Subscriptions()
        renderer.listeners.append(subs.notify)
        port = dlna.HTTP_PORT
        server = dlna.Server(("127.0.0.1", port), dlna.make_handler(renderer, subs))
        threading.Thread(target=server.serve_forever, daemon=True).start()
        base = f"http://127.0.0.1:{port}"

        def get(path):
            return urllib.request.urlopen(base + path, timeout=5).read()

        def soap(service, action, **args):
            inner = "".join(f"<{k}>{v}</{k}>" for k, v in args.items())
            body = ('<?xml version="1.0"?><s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/">'
                    f'<s:Body><u:{action} xmlns:u="{dlna.SERVICES[service]}"><InstanceID>0</InstanceID>'
                    f'{inner}</u:{action}></s:Body></s:Envelope>').encode()
            req = urllib.request.Request(base + f"/{service}/control", data=body, headers={
                "Content-Type": 'text/xml; charset="utf-8"',
                "SOAPACTION": f'"{dlna.SERVICES[service]}#{action}"'})
            try:
                reply = urllib.request.urlopen(req, timeout=5)
                code, text = reply.status, reply.read()
            except urllib.error.HTTPError as e:
                code, text = e.code, e.read()
            root = ElementTree.fromstring(text)
            out = {}
            for el in root.iter():
                if el.tag.endswith("Response"):
                    out = {c.tag: (c.text or "") for c in el}
                if el.tag.endswith("errorCode"):
                    out = {"error": el.text}
            return code, out

        print("descriptions")
        device = ElementTree.fromstring(get("/description.xml"))
        ns = {"d": "urn:schemas-upnp-org:device-1-0"}
        check("it is a media renderer",
              device.find("d:device/d:deviceType", ns).text, dlna.DEVICE_TYPE)
        check("named FreeTVOS", device.find("d:device/d:friendlyName", ns).text, "FreeTVOS")
        check("with its three services", sorted(
            s.text for s in device.findall("d:device/d:serviceList/d:service/d:serviceType", ns)),
            sorted(dlna.SERVICES.values()))
        for name in dlna.SERVICES:
            scpd = ElementTree.fromstring(get(f"/{name}/scpd.xml"))
            sns = {"s": "urn:schemas-upnp-org:service-1-0"}
            declared = {v.text for v in scpd.findall("s:serviceStateTable/s:stateVariable/s:name", sns)}
            used = {r.text for r in scpd.iter("{urn:schemas-upnp-org:service-1-0}relatedStateVariable")}
            check(f"{name}: every argument's variable is declared", used - declared, set())
        check("the same identity every start", dlna.load_uuid(), dlna.UUID)

        print("playing")
        check("nothing loaded at first", soap("AVTransport", "GetTransportInfo")[1]
              ["CurrentTransportState"], "NO_MEDIA_PRESENT")
        check("Play with nothing loaded is refused", soap("AVTransport", "Play", Speed=1)[1],
              {"error": "701"})
        code, _ = soap("AVTransport", "SetAVTransportURI",
                       CurrentURI="http://phone.local/film.mp4&amp;x=1", CurrentURIMetaData="")
        check("an address is accepted, and stopped until Play", (code, renderer.state),
              (200, "STOPPED"))
        soap("AVTransport", "Play", Speed=1)
        check("Play starts it in mpv", player.calls[-1], ("start", "http://phone.local/film.mp4&x=1", 0.0))
        check("and says so", soap("AVTransport", "GetTransportInfo")[1]["CurrentTransportState"],
              "PLAYING")
        pos = soap("AVTransport", "GetPositionInfo")[1]
        check("where it is, as H:MM:SS", (pos["RelTime"], pos["TrackDuration"]),
              ("0:01:23", "1:02:05"))
        soap("AVTransport", "Pause")
        check("Pause pauses mpv", (player.calls[-1], renderer.state),
              (("set", "pause", True), "PAUSED_PLAYBACK"))
        soap("AVTransport", "Play", Speed=1)
        check("and Play resumes it", (player.calls[-1], renderer.state),
              (("set", "pause", False), "PLAYING"))
        soap("AVTransport", "Seek", Unit="REL_TIME", Target="0:10:05.500")
        check("Seek moves mpv", player.calls[-1], ("command", "seek", 605.5, "absolute"))
        check("a seek it cannot read is refused",
              soap("AVTransport", "Seek", Unit="REL_TIME", Target="soon")[1], {"error": "711"})
        soap("AVTransport", "SetAVTransportURI", CurrentURI="http://phone.local/next.mp4",
             CurrentURIMetaData="")
        check("a new address while playing plays at once",
              (player.calls[-1][:2], renderer.state), (("start", "http://phone.local/next.mp4"), "PLAYING"))
        player.alive = False
        renderer.refresh()
        check("mpv closing (the end, or Back) is seen as stopped", renderer.state, "STOPPED")
        soap("AVTransport", "Play", Speed=1)
        soap("AVTransport", "Stop")
        check("Stop stops mpv", (player.alive, renderer.state), (False, "STOPPED"))

        print("volume, formats and actions")
        soap("RenderingControl", "SetVolume", Channel="Master", DesiredVolume=35)
        check("volume", soap("RenderingControl", "GetVolume", Channel="Master")[1],
              {"CurrentVolume": "35"})
        soap("RenderingControl", "SetMute", Channel="Master", DesiredMute=1)
        check("mute", soap("RenderingControl", "GetMute", Channel="Master")[1], {"CurrentMute": "1"})
        sink = soap("ConnectionManager", "GetProtocolInfo")[1]["Sink"]
        check("says it plays MP4 and HLS", ("video/mp4" in sink, "mpegurl" in sink), (True, True))
        check("an unknown action is refused", soap("AVTransport", "Record")[1], {"error": "401"})

        print("events")
        received = []

        class Catcher(http.server.BaseHTTPRequestHandler):
            def do_NOTIFY(self):
                received.append(self.rfile.read(int(self.headers["Content-Length"])).decode())
                self.send_response(200)
                self.end_headers()

            def log_message(self, *a):
                pass

        cport = free_port()
        catcher = http.server.HTTPServer(("127.0.0.1", cport), Catcher)
        threading.Thread(target=catcher.serve_forever, daemon=True).start()
        req = urllib.request.Request(base + "/AVTransport/event", method="SUBSCRIBE", headers={
            "CALLBACK": f"<http://127.0.0.1:{cport}/>", "NT": "upnp:event", "TIMEOUT": "Second-300"})
        reply = urllib.request.urlopen(req, timeout=5)
        check("a subscription is granted", (reply.status, reply.headers["SID"].startswith("uuid:")),
              (200, True))
        soap("AVTransport", "SetAVTransportURI", CurrentURI="http://phone.local/a.mp4",
             CurrentURIMetaData="")
        soap("AVTransport", "Play", Speed=1)
        for _ in range(50):
            if any("PLAYING" in r for r in received):
                break
            time.sleep(0.05)
        check("and told the state now, then when it plays",
              (len(received) >= 2, any("PLAYING" in r for r in received)), (True, True))

        print("discovery")
        replies = dlna.search_replies(dlna.DEVICE_TYPE)
        check("answers a search for a renderer", len(replies), 1)
        check("with where to find it", b"LOCATION: http://" in replies[0], True)
        check("answers ssdp:all for every target", len(dlna.search_replies("ssdp:all")),
              len(dlna.targets()))
        check("and stays quiet for other devices", dlna.search_replies("urn:x:device:Printer:1"), [])
        server.shutdown()

    unit = (REPO / "image/overlay/usr/lib/systemd/system/freetvos-dlna.service").read_text()
    containerfile = (REPO / "image/Containerfile").read_text()
    print("wiring")
    check("runs as the television account, in its session",
          ("User=tv" in unit, "WAYLAND_DISPLAY=wayland-0" in unit), (True, True))
    check("shipped and enabled", ("COPY cast/dlna/" in containerfile,
                                  "freetvos-dlna.service" in containerfile), (True, True))

    if failures:
        print(f"\n{len(failures)} failed")
        return 1
    print("\nall checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
