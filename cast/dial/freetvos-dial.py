#!/usr/bin/env python3
"""A DIAL receiver: the open way for a phone to launch and drive this TV.

There is no legitimate open Chromecast receiver. DIAL is the protocol Cast was
built on top of and is published openly, and the YouTube and Netflix phone apps
still speak it. The phone discovers this device over SSDP, POSTs a pairing
code, and this launches the matching TV web app already defined in
/usr/share/freetvos/webapps. From the user's side it looks like casting.

What it does not do is stream media from the phone. DIAL only launches and
stops an app and hands it a pairing code; the TV then fetches content itself.
For genuine screen mirroring, use the AirPlay receiver instead.

Stdlib only, so it has no packaging burden inside the image.
"""
from __future__ import annotations

import http.server
import logging
import os
import signal
import socket
import struct
import subprocess
import threading
import urllib.parse
import uuid
from pathlib import Path

SSDP_ADDR = "239.255.255.250"
SSDP_PORT = 1900
DIAL_ST = "urn:dial-multiscreen-org:service:dial:1"
HTTP_PORT = int(os.environ.get("FREETVOS_DIAL_PORT", "56789"))
FRIENDLY_NAME = os.environ.get("FREETVOS_NAME", "FreeTVOS")

# DIAL application names are fixed by each vendor's phone app, so they are not
# free to rename. Each maps to a local web app id.
APP_MAP = {"YouTube": "youtube", "Netflix": "netflix"}

# A stable identity across reboots. Phones cache the UUID, and regenerating it
# every start makes the TV appear as a new device each time.
STATE = Path(os.environ.get("STATE_DIRECTORY", "/var/lib/freetvos"))
log = logging.getLogger("dial")


def device_uuid() -> str:
    STATE.mkdir(parents=True, exist_ok=True)
    f = STATE / "dial-uuid"
    if f.exists():
        return f.read_text().strip()
    value = str(uuid.uuid4())
    f.write_text(value)
    return value


def local_ip() -> str:
    """Address on the route toward the LAN, without needing a real send."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("192.0.2.1", 9))  # TEST-NET-1, never routed
        return s.getsockname()[0]
    finally:
        s.close()


UUID = device_uuid()


class AppState:
    """Tracks the one app DIAL allows to be running at a time."""

    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.name: str | None = None
        self.proc: subprocess.Popen | None = None

    def running(self, name: str) -> bool:
        with self.lock:
            return (
                self.name == name
                and self.proc is not None
                and self.proc.poll() is None
            )

    def launch(self, name: str, app_id: str, query: str) -> None:
        self.stop()
        url_extra = f"?{query}" if query else ""
        with self.lock:
            self.name = name
            self.proc = subprocess.Popen(
                ["/usr/bin/freetvos-webapp", app_id],
                env={**os.environ, "FREETVOS_DIAL_QUERY": url_extra},
            )
        log.info("launched %s (%s) with %s", name, app_id, query or "no payload")

    def stop(self) -> None:
        with self.lock:
            if self.proc and self.proc.poll() is None:
                self.proc.terminate()
                try:
                    self.proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    self.proc.kill()
            self.name = None
            self.proc = None


STATE_APP = AppState()


DEVICE_DESC = """<?xml version="1.0"?>
<root xmlns="urn:schemas-upnp-org:device-1-0">
  <specVersion><major>1</major><minor>0</minor></specVersion>
  <device>
    <deviceType>urn:schemas-upnp-org:device:tvdevice:1</deviceType>
    <friendlyName>{name}</friendlyName>
    <manufacturer>FreeTVOS</manufacturer>
    <modelName>FreeTVOS</modelName>
    <UDN>uuid:{uuid}</UDN>
  </device>
</root>
"""


class DialHandler(http.server.BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt, *args):
        log.debug("%s - %s", self.address_string(), fmt % args)

    def _send(self, code: int, body: bytes = b"", ctype: str | None = None,
              extra: dict | None = None) -> None:
        self.send_response(code)
        if ctype:
            self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        if body:
            self.wfile.write(body)

    def do_GET(self) -> None:
        path = urllib.parse.urlparse(self.path).path
        if path == "/dd.xml":
            body = DEVICE_DESC.format(name=FRIENDLY_NAME, uuid=UUID).encode()
            # The Application-URL header is how the client finds the app
            # endpoints; the XML alone is not enough.
            self._send(
                200, body, "application/xml",
                {"Application-URL": f"http://{local_ip()}:{HTTP_PORT}/apps/"},
            )
            return

        if path.startswith("/apps/"):
            name = path[len("/apps/"):].strip("/")
            if name not in APP_MAP:
                self._send(404)
                return
            state = "running" if STATE_APP.running(name) else "stopped"
            body = (
                '<?xml version="1.0" encoding="UTF-8"?>'
                '<service xmlns="urn:dial-multiscreen-org:schemas:dial" '
                'dialVer="2.1">'
                f"<name>{name}</name>"
                f'<options allowStop="true"/>'
                f"<state>{state}</state>"
                "</service>"
            ).encode()
            self._send(200, body, "application/xml")
            return

        self._send(404)

    def do_POST(self) -> None:
        path = urllib.parse.urlparse(self.path).path
        if not path.startswith("/apps/"):
            self._send(404)
            return
        name = path[len("/apps/"):].strip("/")
        if name not in APP_MAP:
            self._send(404)
            return

        length = int(self.headers.get("Content-Length") or 0)
        payload = self.rfile.read(length).decode("utf-8", "replace") if length else ""
        STATE_APP.launch(name, APP_MAP[name], payload)
        self._send(
            201, b"", None,
            {"LOCATION": f"http://{local_ip()}:{HTTP_PORT}/apps/{name}/run"},
        )

    def do_DELETE(self) -> None:
        path = urllib.parse.urlparse(self.path).path
        if path.startswith("/apps/") and path.endswith("/run"):
            STATE_APP.stop()
            self._send(200)
            return
        self._send(404)


def ssdp_responder(stop: threading.Event) -> None:
    """Answer only DIAL discovery, leaving general UPnP traffic alone."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(("", SSDP_PORT))
    mreq = struct.pack("4sl", socket.inet_aton(SSDP_ADDR), socket.INADDR_ANY)
    sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)
    sock.settimeout(1.0)
    log.info("SSDP responder listening on %s:%d", SSDP_ADDR, SSDP_PORT)

    while not stop.is_set():
        try:
            data, addr = sock.recvfrom(2048)
        except socket.timeout:
            continue
        except OSError:
            break
        text = data.decode("utf-8", "replace")
        if not text.startswith("M-SEARCH") or DIAL_ST not in text:
            continue
        reply = (
            "HTTP/1.1 200 OK\r\n"
            "CACHE-CONTROL: max-age=1800\r\n"
            "EXT:\r\n"
            f"LOCATION: http://{local_ip()}:{HTTP_PORT}/dd.xml\r\n"
            "SERVER: Linux/6 UPnP/1.1 FreeTVOS/1.0\r\n"
            f"ST: {DIAL_ST}\r\n"
            f"USN: uuid:{UUID}::{DIAL_ST}\r\n"
            "\r\n"
        ).encode()
        sock.sendto(reply, addr)
        log.info("discovery answered for %s", addr[0])
    sock.close()


def main() -> None:
    logging.basicConfig(
        level=os.environ.get("FREETVOS_LOG", "INFO"),
        format="%(levelname)s %(name)s: %(message)s",
    )
    stop = threading.Event()
    threading.Thread(target=ssdp_responder, args=(stop,), daemon=True).start()

    server = http.server.ThreadingHTTPServer(("", HTTP_PORT), DialHandler)
    log.info("DIAL endpoint on port %d as %r", HTTP_PORT, FRIENDLY_NAME)

    def shutdown(*_):
        stop.set()
        STATE_APP.stop()
        threading.Thread(target=server.shutdown, daemon=True).start()

    signal.signal(signal.SIGTERM, shutdown)
    signal.signal(signal.SIGINT, shutdown)
    server.serve_forever()


if __name__ == "__main__":
    main()
