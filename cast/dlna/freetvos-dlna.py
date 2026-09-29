#!/usr/bin/env python3
"""A DLNA/UPnP media renderer: cast a video from a phone app to this TV.

Chromecast cannot be received openly (every Cast app checks for a
Google-signed device certificate), and AirPlay's video mode is FairPlay for
most apps and YouTube-only in UxPlay. DLNA is the open standard for "play this
address on that screen", and many apps speak it as senders: Web Video Caster,
VLC and BubbleUPnP on Android, phone galleries and file managers, and media
servers. This renderer appears to them as FreeTVOS and plays what they send full
screen in mpv, which is already on the television and plays nearly anything.

  AVTransport       load an address, play, pause, stop, seek, and say where
                    playback is, which is what a sender's scrub bar shows
  RenderingControl  volume and mute
  ConnectionManager what can be played

Senders find it over SSDP and mostly poll for state; the ones that subscribe to
events are sent LastChange notifications as the state changes.

Stdlib only, like the DIAL receiver beside it, so it adds nothing to package.
mpv is driven through its JSON IPC socket.
"""
from __future__ import annotations

import html
import http.server
import json
import logging
import os
import re
import signal
import socket
import socketserver
import struct
import subprocess
import threading
import time
import urllib.parse
import urllib.request
import uuid
from pathlib import Path
from xml.etree import ElementTree

log = logging.getLogger("dlna")

SSDP_ADDR = "239.255.255.250"
SSDP_PORT = 1900
HTTP_PORT = int(os.environ.get("FREETVOS_DLNA_PORT", "49494"))
FRIENDLY_NAME = os.environ.get("FREETVOS_NAME", "FreeTVOS")
STATE_DIR = Path(os.environ.get("STATE_DIRECTORY", "/var/lib/freetvos"))
RUNTIME = Path(os.environ.get("XDG_RUNTIME_DIR", f"/run/user/{os.getuid()}"))
MPV = os.environ.get("FREETVOS_DLNA_MPV", "mpv")
MAX_AGE = 1800

DEVICE_TYPE = "urn:schemas-upnp-org:device:MediaRenderer:1"
AVT = "urn:schemas-upnp-org:service:AVTransport:1"
RC = "urn:schemas-upnp-org:service:RenderingControl:1"
CM = "urn:schemas-upnp-org:service:ConnectionManager:1"
SERVICES = {"AVTransport": AVT, "RenderingControl": RC, "ConnectionManager": CM}

# What senders are told this can play. mpv plays far more; senders use this to
# decide whether to offer the television at all, so it lists the common kinds
# and ends with a catch-all.
SINK_PROTOCOLS = ",".join(
    f"http-get:*:{mime}:*" for mime in (
        "video/mp4", "video/x-matroska", "video/webm", "video/mpeg", "video/mp2t",
        "video/quicktime", "video/x-msvideo", "video/x-flv", "video/3gpp",
        "application/vnd.apple.mpegurl", "application/x-mpegurl",
        "audio/mpeg", "audio/mp4", "audio/aac", "audio/flac", "audio/x-flac",
        "audio/wav", "audio/x-wav", "audio/ogg", "audio/opus",
        "image/jpeg", "image/png", "image/gif", "image/webp", "*"))


def load_uuid() -> str:
    """A stable identity: senders remember a renderer by it."""
    path = STATE_DIR / "dlna-uuid"
    try:
        return path.read_text().strip()
    except OSError:
        value = str(uuid.uuid4())
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(value + "\n")
        except OSError:
            pass
        return value


UUID = load_uuid()


def local_ip() -> str:
    """The address senders on the home network reach this television at."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("192.0.2.1", 9))  # never sent: only picks the outgoing interface
        return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        s.close()


# ---------------------------------------------------------------------------
# Time, as UPnP writes it.
# ---------------------------------------------------------------------------


def hms(seconds) -> str:
    """Seconds as H:MM:SS, the only form every sender reads."""
    if seconds is None:
        return "0:00:00"
    seconds = max(0, int(seconds))
    return f"{seconds // 3600}:{seconds // 60 % 60:02d}:{seconds % 60:02d}"


def parse_hms(text: str) -> float:
    """H:MM:SS, H:MM:SS.fff or plain seconds, as a sender may send a seek."""
    text = (text or "").strip()
    if re.fullmatch(r"\d+(\.\d+)?", text):
        return float(text)
    match = re.fullmatch(r"(\d+):(\d{1,2}):(\d{1,2}(?:\.\d+)?)", text)
    if not match:
        raise ValueError(text)
    h, m, s = match.groups()
    return int(h) * 3600 + int(m) * 60 + float(s)


# ---------------------------------------------------------------------------
# mpv.
# ---------------------------------------------------------------------------


class Player:
    """One mpv at a time, full screen, driven over its IPC socket.

    mpv quits at the end of what it was given, and that is how a renderer
    learns playback has stopped. Kept small so the tests can replace it.
    """

    def __init__(self):
        self.proc: subprocess.Popen | None = None
        self.sock = RUNTIME / "freetvos-dlna-mpv.sock"
        self.volume = 100
        self.muted = False
        self.lock = threading.RLock()

    def running(self) -> bool:
        return self.proc is not None and self.proc.poll() is None

    def start(self, uri: str, position: float = 0.0) -> None:
        with self.lock:
            self.stop()
            try:
                self.sock.unlink()
            except OSError:
                pass
            args = [MPV, "--fullscreen", "--no-terminal", "--force-window=immediate",
                    "--keep-open=no", "--idle=no", "--ytdl=no", "--hwdec=auto-safe",
                    "--title=FreeTVOS", "--wayland-app-id=freetvos-cast",
                    f"--input-ipc-server={self.sock}", f"--volume={self.volume}",
                    f"--mute={'yes' if self.muted else 'no'}"]
            if position:
                args.append(f"--start={position:.3f}")
            args += ["--", uri]
            log.info("playing %s", uri)
            self.proc = subprocess.Popen(args, stdin=subprocess.DEVNULL,
                                         stdout=subprocess.DEVNULL,
                                         stderr=subprocess.DEVNULL)
            for _ in range(50):
                if self.sock.exists() or not self.running():
                    break
                time.sleep(0.1)

    def stop(self) -> None:
        with self.lock:
            if self.running():
                self.command("quit")
                try:
                    self.proc.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    self.proc.kill()
            self.proc = None

    def command(self, *args):
        """Send one command; its data, or None if mpv is not answering."""
        if not self.running():
            return None
        try:
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
                s.settimeout(2)
                s.connect(str(self.sock))
                s.sendall(json.dumps({"command": list(args), "request_id": 1}).encode() + b"\n")
                buffer = b""
                while True:
                    chunk = s.recv(65536)
                    if not chunk:
                        return None
                    buffer += chunk
                    while b"\n" in buffer:
                        line, buffer = buffer.split(b"\n", 1)
                        reply = json.loads(line or b"{}")
                        if reply.get("request_id") == 1:
                            return reply.get("data") if reply.get("error") == "success" else None
        except (OSError, ValueError):
            return None

    def get(self, name):
        return self.command("get_property", name)

    def set(self, name, value) -> None:
        self.command("set_property", name, value)

    def set_volume(self, volume: int) -> None:
        self.volume = max(0, min(100, int(volume)))
        self.set("volume", self.volume)

    def set_mute(self, muted: bool) -> None:
        self.muted = bool(muted)
        self.set("mute", self.muted)


# ---------------------------------------------------------------------------
# The renderer's state, and what changes it.
# ---------------------------------------------------------------------------


class Renderer:
    def __init__(self, player):
        self.player = player
        self.lock = threading.RLock()
        self.uri = ""
        self.metadata = ""
        self.state = "NO_MEDIA_PRESENT"
        self.listeners = []  # called with (service, {variable: value})

    # What a sender sees.
    def position(self) -> tuple:
        """(elapsed, duration) in seconds, 0 when not known."""
        if not self.player.running():
            return 0.0, 0.0
        return (float(self.player.get("time-pos") or 0.0),
                float(self.player.get("duration") or 0.0))

    def refresh(self) -> None:
        """Notice mpv having finished by itself, or been closed with Back."""
        with self.lock:
            if self.state in ("PLAYING", "PAUSED_PLAYBACK") and not self.player.running():
                self.change("STOPPED")

    def change(self, state: str) -> None:
        with self.lock:
            if state == self.state:
                return
            self.state = state
        log.info("state %s", state)
        self.emit("AVTransport", {"TransportState": state})

    def emit(self, service: str, variables: dict) -> None:
        for listener in list(self.listeners):
            try:
                listener(service, variables)
            except Exception:  # noqa: BLE001 - a bad subscriber must not stop playback
                log.exception("event listener failed")

    # What a sender asks for.
    def set_uri(self, uri: str, metadata: str) -> None:
        with self.lock:
            playing = self.state in ("PLAYING", "PAUSED_PLAYBACK")
            self.uri, self.metadata = uri, metadata
            self.emit("AVTransport", {"AVTransportURI": uri, "CurrentTrackURI": uri})
            if playing:
                # Changing what plays while playing: play the new one, as a
                # television does, rather than stopping and waiting for Play.
                self.player.start(uri)
                self.change("PLAYING")
            else:
                self.player.stop()
                self.change("STOPPED")

    def play(self) -> None:
        with self.lock:
            if not self.uri:
                raise UPnPError(701, "No media to play")
            if self.state == "PAUSED_PLAYBACK" and self.player.running():
                self.player.set("pause", False)
            elif not self.player.running():
                self.change("TRANSITIONING")
                self.player.start(self.uri)
            self.change("PLAYING")

    def pause(self) -> None:
        with self.lock:
            if self.player.running():
                self.player.set("pause", True)
                self.change("PAUSED_PLAYBACK")

    def stop(self) -> None:
        with self.lock:
            self.player.stop()
            self.change("STOPPED" if self.uri else "NO_MEDIA_PRESENT")

    def seek(self, unit: str, target: str) -> None:
        if unit not in ("REL_TIME", "ABS_TIME", "ABS_COUNT", "REL_COUNT"):
            raise UPnPError(710, "Seek mode not supported")
        try:
            seconds = parse_hms(target)
        except ValueError:
            raise UPnPError(711, "Illegal seek target") from None
        with self.lock:
            if self.player.running():
                self.player.command("seek", seconds, "absolute")
            elif self.uri:
                self.player.start(self.uri, seconds)
                self.change("PLAYING")


class UPnPError(Exception):
    def __init__(self, code: int, text: str):
        super().__init__(text)
        self.code, self.text = code, text


# ---------------------------------------------------------------------------
# SOAP actions.
# ---------------------------------------------------------------------------


def action(renderer: Renderer, service: str, name: str, args: dict) -> dict:
    """Run one action; the response's arguments, in order."""
    player = renderer.player
    if service == "AVTransport":
        if name == "SetAVTransportURI":
            renderer.set_uri(args.get("CurrentURI", ""), args.get("CurrentURIMetaData", ""))
            return {}
        if name == "SetNextAVTransportURI":
            return {}  # accepted and ignored: one thing at a time
        if name == "Play":
            renderer.play()
            return {}
        if name == "Pause":
            renderer.pause()
            return {}
        if name == "Stop":
            renderer.stop()
            return {}
        if name == "Seek":
            renderer.seek(args.get("Unit", ""), args.get("Target", ""))
            return {}
        if name == "GetTransportInfo":
            renderer.refresh()
            return {"CurrentTransportState": renderer.state,
                    "CurrentTransportStatus": "OK", "CurrentSpeed": "1"}
        if name == "GetPositionInfo":
            renderer.refresh()
            elapsed, duration = renderer.position()
            return {"Track": "1" if renderer.uri else "0",
                    "TrackDuration": hms(duration), "TrackMetaData": renderer.metadata,
                    "TrackURI": renderer.uri, "RelTime": hms(elapsed),
                    "AbsTime": hms(elapsed), "RelCount": "2147483647",
                    "AbsCount": "2147483647"}
        if name == "GetMediaInfo":
            _, duration = renderer.position()
            return {"NrTracks": "1" if renderer.uri else "0",
                    "MediaDuration": hms(duration), "CurrentURI": renderer.uri,
                    "CurrentURIMetaData": renderer.metadata, "NextURI": "",
                    "NextURIMetaData": "", "PlayMedium": "NETWORK",
                    "RecordMedium": "NOT_IMPLEMENTED", "WriteStatus": "NOT_IMPLEMENTED"}
        if name == "GetTransportSettings":
            return {"PlayMode": "NORMAL", "RecQualityMode": "NOT_IMPLEMENTED"}
        if name == "GetDeviceCapabilities":
            return {"PlayMedia": "NETWORK", "RecMedia": "NOT_IMPLEMENTED",
                    "RecQualityModes": "NOT_IMPLEMENTED"}
        if name == "GetCurrentTransportActions":
            return {"Actions": "Play,Pause,Stop,Seek"}
    elif service == "RenderingControl":
        if name == "GetVolume":
            return {"CurrentVolume": str(player.volume)}
        if name == "SetVolume":
            try:
                player.set_volume(int(args.get("DesiredVolume", "")))
            except ValueError:
                raise UPnPError(402, "Invalid volume") from None
            renderer.emit("RenderingControl", {"Volume": str(player.volume)})
            return {}
        if name == "GetMute":
            return {"CurrentMute": "1" if player.muted else "0"}
        if name == "SetMute":
            player.set_mute(args.get("DesiredMute", "0").lower() in ("1", "true", "yes"))
            renderer.emit("RenderingControl", {"Mute": "1" if player.muted else "0"})
            return {}
        if name == "ListPresets":
            return {"CurrentPresetNameList": "FactoryDefaults"}
        if name == "SelectPreset":
            return {}
    elif service == "ConnectionManager":
        if name == "GetProtocolInfo":
            return {"Source": "", "Sink": SINK_PROTOCOLS}
        if name == "GetCurrentConnectionIDs":
            return {"ConnectionIDs": "0"}
        if name == "GetCurrentConnectionInfo":
            return {"RcsID": "0", "AVTransportID": "0", "ProtocolInfo": "",
                    "PeerConnectionManager": "", "PeerConnectionID": "-1",
                    "Direction": "Input", "Status": "OK"}
    raise UPnPError(401, "Invalid Action")


def parse_soap(body: bytes) -> tuple:
    """(action name, {argument: value}) from a SOAP request body."""
    root = ElementTree.fromstring(body)
    for element in root.iter():
        if element.tag.endswith("}Body"):
            request = next(iter(element), None)
            if request is None:
                break
            name = request.tag.split("}")[-1]
            args = {child.tag.split("}")[-1]: (child.text or "") for child in request}
            return name, args
    raise ValueError("no SOAP body")


def soap_response(service_type: str, name: str, values: dict) -> bytes:
    inner = "".join(f"<{k}>{html.escape(v, quote=False)}</{k}>" for k, v in values.items())
    return ('<?xml version="1.0" encoding="utf-8"?>'
            '<s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/" '
            's:encodingStyle="http://schemas.xmlsoap.org/soap/encoding/"><s:Body>'
            f'<u:{name}Response xmlns:u="{service_type}">{inner}</u:{name}Response>'
            '</s:Body></s:Envelope>').encode()


def soap_fault(code: int, text: str) -> bytes:
    return ('<?xml version="1.0" encoding="utf-8"?>'
            '<s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/" '
            's:encodingStyle="http://schemas.xmlsoap.org/soap/encoding/"><s:Body><s:Fault>'
            '<faultcode>s:Client</faultcode><faultstring>UPnPError</faultstring><detail>'
            '<UPnPError xmlns="urn:schemas-upnp-org:control-1-0">'
            f'<errorCode>{code}</errorCode><errorDescription>{html.escape(text)}'
            '</errorDescription></UPnPError></detail></s:Fault></s:Body></s:Envelope>').encode()


# ---------------------------------------------------------------------------
# Descriptions.
# ---------------------------------------------------------------------------


DEVICE_XML = """<?xml version="1.0" encoding="utf-8"?>
<root xmlns="urn:schemas-upnp-org:device-1-0" xmlns:dlna="urn:schemas-dlna-org:device-1-0">
  <specVersion><major>1</major><minor>0</minor></specVersion>
  <device>
    <deviceType>{device_type}</deviceType>
    <friendlyName>{name}</friendlyName>
    <manufacturer>FreeTVOS</manufacturer>
    <manufacturerURL>https://github.com/leesander1/freetvos</manufacturerURL>
    <modelDescription>FreeTVOS media renderer</modelDescription>
    <modelName>FreeTVOS</modelName>
    <modelNumber>1</modelNumber>
    <UDN>uuid:{uuid}</UDN>
    <dlna:X_DLNADOC>DMR-1.50</dlna:X_DLNADOC>
    <serviceList>{services}
    </serviceList>
  </device>
</root>
"""

SERVICE_XML = """
      <service>
        <serviceType>{type}</serviceType>
        <serviceId>urn:upnp-org:serviceId:{name}</serviceId>
        <SCPDURL>/{name}/scpd.xml</SCPDURL>
        <controlURL>/{name}/control</controlURL>
        <eventSubURL>/{name}/event</eventSubURL>
      </service>"""

# Each action: (name, [(argument, direction, related state variable)]).
ACTIONS = {
    "AVTransport": [
        ("SetAVTransportURI", [("InstanceID", "in", "A_ARG_TYPE_InstanceID"),
                               ("CurrentURI", "in", "AVTransportURI"),
                               ("CurrentURIMetaData", "in", "AVTransportURIMetaData")]),
        ("SetNextAVTransportURI", [("InstanceID", "in", "A_ARG_TYPE_InstanceID"),
                                   ("NextURI", "in", "NextAVTransportURI"),
                                   ("NextURIMetaData", "in", "NextAVTransportURIMetaData")]),
        ("GetMediaInfo", [("InstanceID", "in", "A_ARG_TYPE_InstanceID"),
                          ("NrTracks", "out", "NumberOfTracks"),
                          ("MediaDuration", "out", "CurrentMediaDuration"),
                          ("CurrentURI", "out", "AVTransportURI"),
                          ("CurrentURIMetaData", "out", "AVTransportURIMetaData"),
                          ("NextURI", "out", "NextAVTransportURI"),
                          ("NextURIMetaData", "out", "NextAVTransportURIMetaData"),
                          ("PlayMedium", "out", "PlaybackStorageMedium"),
                          ("RecordMedium", "out", "RecordStorageMedium"),
                          ("WriteStatus", "out", "RecordMediumWriteStatus")]),
        ("GetTransportInfo", [("InstanceID", "in", "A_ARG_TYPE_InstanceID"),
                              ("CurrentTransportState", "out", "TransportState"),
                              ("CurrentTransportStatus", "out", "TransportStatus"),
                              ("CurrentSpeed", "out", "TransportPlaySpeed")]),
        ("GetPositionInfo", [("InstanceID", "in", "A_ARG_TYPE_InstanceID"),
                             ("Track", "out", "CurrentTrack"),
                             ("TrackDuration", "out", "CurrentTrackDuration"),
                             ("TrackMetaData", "out", "CurrentTrackMetaData"),
                             ("TrackURI", "out", "CurrentTrackURI"),
                             ("RelTime", "out", "RelativeTimePosition"),
                             ("AbsTime", "out", "AbsoluteTimePosition"),
                             ("RelCount", "out", "RelativeCounterPosition"),
                             ("AbsCount", "out", "AbsoluteCounterPosition")]),
        ("GetDeviceCapabilities", [("InstanceID", "in", "A_ARG_TYPE_InstanceID"),
                                   ("PlayMedia", "out", "PossiblePlaybackStorageMedia"),
                                   ("RecMedia", "out", "PossibleRecordStorageMedia"),
                                   ("RecQualityModes", "out", "PossibleRecordQualityModes")]),
        ("GetTransportSettings", [("InstanceID", "in", "A_ARG_TYPE_InstanceID"),
                                  ("PlayMode", "out", "CurrentPlayMode"),
                                  ("RecQualityMode", "out", "CurrentRecordQualityMode")]),
        ("Stop", [("InstanceID", "in", "A_ARG_TYPE_InstanceID")]),
        ("Play", [("InstanceID", "in", "A_ARG_TYPE_InstanceID"),
                  ("Speed", "in", "TransportPlaySpeed")]),
        ("Pause", [("InstanceID", "in", "A_ARG_TYPE_InstanceID")]),
        ("Seek", [("InstanceID", "in", "A_ARG_TYPE_InstanceID"),
                  ("Unit", "in", "A_ARG_TYPE_SeekMode"),
                  ("Target", "in", "A_ARG_TYPE_SeekTarget")]),
        ("GetCurrentTransportActions", [("InstanceID", "in", "A_ARG_TYPE_InstanceID"),
                                        ("Actions", "out", "CurrentTransportActions")]),
    ],
    "RenderingControl": [
        ("ListPresets", [("InstanceID", "in", "A_ARG_TYPE_InstanceID"),
                         ("CurrentPresetNameList", "out", "PresetNameList")]),
        ("SelectPreset", [("InstanceID", "in", "A_ARG_TYPE_InstanceID"),
                          ("PresetName", "in", "A_ARG_TYPE_PresetName")]),
        ("GetMute", [("InstanceID", "in", "A_ARG_TYPE_InstanceID"),
                     ("Channel", "in", "A_ARG_TYPE_Channel"),
                     ("CurrentMute", "out", "Mute")]),
        ("SetMute", [("InstanceID", "in", "A_ARG_TYPE_InstanceID"),
                     ("Channel", "in", "A_ARG_TYPE_Channel"),
                     ("DesiredMute", "in", "Mute")]),
        ("GetVolume", [("InstanceID", "in", "A_ARG_TYPE_InstanceID"),
                       ("Channel", "in", "A_ARG_TYPE_Channel"),
                       ("CurrentVolume", "out", "Volume")]),
        ("SetVolume", [("InstanceID", "in", "A_ARG_TYPE_InstanceID"),
                       ("Channel", "in", "A_ARG_TYPE_Channel"),
                       ("DesiredVolume", "in", "Volume")]),
    ],
    "ConnectionManager": [
        ("GetProtocolInfo", [("Source", "out", "SourceProtocolInfo"),
                             ("Sink", "out", "SinkProtocolInfo")]),
        ("GetCurrentConnectionIDs", [("ConnectionIDs", "out", "CurrentConnectionIDs")]),
        ("GetCurrentConnectionInfo", [
            ("ConnectionID", "in", "A_ARG_TYPE_ConnectionID"),
            ("RcsID", "out", "A_ARG_TYPE_RcsID"),
            ("AVTransportID", "out", "A_ARG_TYPE_AVTransportID"),
            ("ProtocolInfo", "out", "A_ARG_TYPE_ProtocolInfo"),
            ("PeerConnectionManager", "out", "A_ARG_TYPE_ConnectionManager"),
            ("PeerConnectionID", "out", "A_ARG_TYPE_ConnectionID"),
            ("Direction", "out", "A_ARG_TYPE_Direction"),
            ("Status", "out", "A_ARG_TYPE_ConnectionStatus")]),
    ],
}

# State variables: name -> (data type, sends events, allowed values).
EVENTED = {"LastChange", "SourceProtocolInfo", "SinkProtocolInfo", "CurrentConnectionIDs"}
TYPES = {"Volume": "ui2", "A_ARG_TYPE_InstanceID": "ui4", "NumberOfTracks": "ui4",
         "CurrentTrack": "ui4", "RelativeCounterPosition": "i4",
         "AbsoluteCounterPosition": "i4", "Mute": "boolean", "A_ARG_TYPE_ConnectionID": "i4",
         "A_ARG_TYPE_RcsID": "i4", "A_ARG_TYPE_AVTransportID": "i4"}
ALLOWED = {
    "TransportState": ["STOPPED", "PLAYING", "PAUSED_PLAYBACK", "TRANSITIONING",
                       "NO_MEDIA_PRESENT"],
    "TransportStatus": ["OK", "ERROR_OCCURRED"],
    "A_ARG_TYPE_SeekMode": ["REL_TIME", "ABS_TIME", "ABS_COUNT", "REL_COUNT"],
    "A_ARG_TYPE_Channel": ["Master"],
    "A_ARG_TYPE_PresetName": ["FactoryDefaults"],
    "A_ARG_TYPE_Direction": ["Input", "Output"],
    "CurrentPlayMode": ["NORMAL"],
}


def scpd(service: str) -> str:
    actions = ACTIONS[service]
    variables = sorted({var for _, args in actions for _, _, var in args} | {"LastChange"}
                       if service != "ConnectionManager"
                       else {var for _, args in actions for _, _, var in args})
    out = ['<?xml version="1.0" encoding="utf-8"?>',
           '<scpd xmlns="urn:schemas-upnp-org:service-1-0">',
           "<specVersion><major>1</major><minor>0</minor></specVersion><actionList>"]
    for name, args in actions:
        out.append(f"<action><name>{name}</name><argumentList>")
        for arg, direction, var in args:
            out.append(f"<argument><name>{arg}</name><direction>{direction}</direction>"
                       f"<relatedStateVariable>{var}</relatedStateVariable></argument>")
        out.append("</argumentList></action>")
    out.append("</actionList><serviceStateTable>")
    for var in variables:
        events = "yes" if var in EVENTED else "no"
        out.append(f'<stateVariable sendEvents="{events}"><name>{var}</name>'
                   f"<dataType>{TYPES.get(var, 'string')}</dataType>")
        if var in ALLOWED:
            out.append("<allowedValueList>" + "".join(
                f"<allowedValue>{v}</allowedValue>" for v in ALLOWED[var])
                + "</allowedValueList>")
        if var == "Volume":
            out.append("<allowedValueRange><minimum>0</minimum><maximum>100</maximum>"
                       "<step>1</step></allowedValueRange>")
        out.append("</stateVariable>")
    out.append("</serviceStateTable></scpd>")
    return "".join(out)


def device_xml() -> str:
    services = "".join(SERVICE_XML.format(type=t, name=n) for n, t in SERVICES.items())
    return DEVICE_XML.format(device_type=DEVICE_TYPE, name=html.escape(FRIENDLY_NAME),
                             uuid=UUID, services=services)


# ---------------------------------------------------------------------------
# Events.
# ---------------------------------------------------------------------------


NAMESPACES = {"AVTransport": "urn:schemas-upnp-org:metadata-1-0/AVT/",
              "RenderingControl": "urn:schemas-upnp-org:metadata-1-0/RCS/"}


def last_change(service: str, variables: dict) -> bytes:
    channel = ' channel="Master"' if service == "RenderingControl" else ""
    inner = "".join(f'<{k}{channel if k in ("Volume", "Mute") else ""} val="{html.escape(v)}"/>'
                    for k, v in variables.items())
    event = f'<Event xmlns="{NAMESPACES[service]}"><InstanceID val="0">{inner}</InstanceID></Event>'
    return ('<?xml version="1.0" encoding="utf-8"?>'
            '<e:propertyset xmlns:e="urn:schemas-upnp-org:event-1-0"><e:property>'
            f"<LastChange>{html.escape(event)}</LastChange>"
            "</e:property></e:propertyset>").encode()


class Subscriptions:
    """Senders that asked to be told of changes, per service."""

    def __init__(self):
        self.lock = threading.Lock()
        self.subs = {}  # sid -> {"service", "urls", "expires", "seq"}

    def add(self, service: str, callback: str, timeout: int) -> str:
        urls = re.findall(r"<([^>]+)>", callback)
        sid = f"uuid:{uuid.uuid4()}"
        with self.lock:
            self.subs[sid] = {"service": service, "urls": urls,
                              "expires": time.time() + timeout, "seq": 0}
        return sid

    def renew(self, sid: str, timeout: int) -> bool:
        with self.lock:
            if sid not in self.subs:
                return False
            self.subs[sid]["expires"] = time.time() + timeout
            return True

    def remove(self, sid: str) -> None:
        with self.lock:
            self.subs.pop(sid, None)

    def notify(self, service: str, variables: dict, only: str | None = None) -> None:
        if service not in NAMESPACES:
            return
        body = last_change(service, variables)
        now = time.time()
        with self.lock:
            targets = []
            for sid, sub in list(self.subs.items()):
                if sub["expires"] < now:
                    del self.subs[sid]
                elif sub["service"] == service and (only is None or sid == only):
                    targets.append((sid, list(sub["urls"]), sub["seq"]))
                    sub["seq"] += 1
        for sid, urls, seq in targets:
            threading.Thread(target=self._send, args=(urls, sid, seq, body),
                             daemon=True).start()

    @staticmethod
    def _send(urls, sid, seq, body) -> None:
        for url in urls:
            request = urllib.request.Request(url, data=body, method="NOTIFY", headers={
                "Content-Type": 'text/xml; charset="utf-8"', "NT": "upnp:event",
                "NTS": "upnp:propchange", "SID": sid, "SEQ": str(seq)})
            try:
                urllib.request.urlopen(request, timeout=3).close()
                return
            except OSError:
                continue


# ---------------------------------------------------------------------------
# HTTP.
# ---------------------------------------------------------------------------


def make_handler(renderer: Renderer, subscriptions: Subscriptions):
    class Handler(http.server.BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"
        server_version = "FreeTVOS-DLNA/1.0"

        def log_message(self, fmt, *args):
            log.debug("%s %s", self.address_string(), fmt % args)

        def _send(self, code, body=b"", ctype="text/xml; charset=\"utf-8\"", headers=None):
            self.send_response(code)
            if body:
                self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            for key, value in (headers or {}).items():
                self.send_header(key, value)
            self.end_headers()
            if body and self.command != "HEAD":
                self.wfile.write(body)

        def do_GET(self):
            path = urllib.parse.urlparse(self.path).path
            if path in ("/", "/description.xml"):
                return self._send(200, device_xml().encode())
            match = re.fullmatch(r"/(\w+)/scpd\.xml", path)
            if match and match.group(1) in SERVICES:
                return self._send(200, scpd(match.group(1)).encode())
            return self._send(404)

        do_HEAD = do_GET

        def do_POST(self):
            match = re.fullmatch(r"/(\w+)/control", urllib.parse.urlparse(self.path).path)
            if not match or match.group(1) not in SERVICES:
                return self._send(404)
            service = match.group(1)
            body = self.rfile.read(int(self.headers.get("Content-Length") or 0))
            try:
                name, args = parse_soap(body)
            except (ElementTree.ParseError, ValueError):
                return self._send(500, soap_fault(402, "Invalid Args"))
            try:
                values = action(renderer, service, name, args)
            except UPnPError as e:
                log.info("%s %s refused: %s", service, name, e.text)
                return self._send(500, soap_fault(e.code, e.text))
            log.debug("%s %s %s", service, name, args)
            return self._send(200, soap_response(SERVICES[service], name, values))

        def do_SUBSCRIBE(self):
            match = re.fullmatch(r"/(\w+)/event", urllib.parse.urlparse(self.path).path)
            if not match or match.group(1) not in SERVICES:
                return self._send(404)
            service = match.group(1)
            timeout = 1800
            found = re.search(r"Second-(\d+)", self.headers.get("TIMEOUT", ""))
            if found:
                timeout = max(60, min(int(found.group(1)), 86400))
            sid = self.headers.get("SID")
            if sid:
                if not subscriptions.renew(sid, timeout):
                    return self._send(412)
            else:
                callback = self.headers.get("CALLBACK", "")
                if not callback:
                    return self._send(412)
                sid = subscriptions.add(service, callback, timeout)
            self._send(200, headers={"SID": sid, "TIMEOUT": f"Second-{timeout}"})
            # The first event tells a new subscriber where things stand.
            if not self.headers.get("SID"):
                if service == "AVTransport":
                    subscriptions.notify(service, {
                        "TransportState": renderer.state, "AVTransportURI": renderer.uri,
                        "CurrentTrackURI": renderer.uri,
                        "CurrentTransportActions": "Play,Pause,Stop,Seek"}, only=sid)
                elif service == "RenderingControl":
                    subscriptions.notify(service, {
                        "Volume": str(renderer.player.volume),
                        "Mute": "1" if renderer.player.muted else "0"}, only=sid)

        def do_UNSUBSCRIBE(self):
            subscriptions.remove(self.headers.get("SID", ""))
            self._send(200)

    return Handler


class Server(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True
    allow_reuse_address = True


# ---------------------------------------------------------------------------
# SSDP.
# ---------------------------------------------------------------------------


def targets() -> list:
    """(NT or ST, USN) for everything this device answers to."""
    base = f"uuid:{UUID}"
    out = [("upnp:rootdevice", f"{base}::upnp:rootdevice"), (base, base),
           (DEVICE_TYPE, f"{base}::{DEVICE_TYPE}")]
    out += [(t, f"{base}::{t}") for t in SERVICES.values()]
    return out


def location() -> str:
    return f"http://{local_ip()}:{HTTP_PORT}/description.xml"


def search_replies(search_target: str) -> list:
    """The M-SEARCH replies for one search, or none if it is not for us."""
    wanted = [(nt, usn) for nt, usn in targets()
              if search_target == "ssdp:all" or search_target == nt]
    return [("HTTP/1.1 200 OK\r\n"
             f"CACHE-CONTROL: max-age={MAX_AGE}\r\nEXT:\r\n"
             f"LOCATION: {location()}\r\n"
             "SERVER: Linux/6 UPnP/1.0 FreeTVOS-DLNA/1.0\r\n"
             f"ST: {nt}\r\nUSN: {usn}\r\n\r\n").encode() for nt, usn in wanted]


def notify(kind: str) -> None:
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 2)
    try:
        for nt, usn in targets():
            lines = [f"NOTIFY * HTTP/1.1", f"HOST: {SSDP_ADDR}:{SSDP_PORT}",
                     f"NT: {nt}", f"NTS: ssdp:{kind}", f"USN: {usn}"]
            if kind == "alive":
                lines += [f"CACHE-CONTROL: max-age={MAX_AGE}", f"LOCATION: {location()}",
                          "SERVER: Linux/6 UPnP/1.0 FreeTVOS-DLNA/1.0"]
            sock.sendto(("\r\n".join(lines) + "\r\n\r\n").encode(), (SSDP_ADDR, SSDP_PORT))
    except OSError as e:
        log.warning("SSDP %s failed: %s", kind, e)
    finally:
        sock.close()


def ssdp_responder(stop: threading.Event) -> None:
    """Answer searches for a renderer. The DIAL receiver shares port 1900."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    if hasattr(socket, "SO_REUSEPORT"):
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
    sock.bind(("", SSDP_PORT))
    mreq = struct.pack("4sl", socket.inet_aton(SSDP_ADDR), socket.INADDR_ANY)
    sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)
    sock.settimeout(1.0)
    while not stop.is_set():
        try:
            data, addr = sock.recvfrom(4096)
        except socket.timeout:
            continue
        except OSError:
            break
        text = data.decode("utf-8", "replace")
        if not text.startswith("M-SEARCH"):
            continue
        found = re.search(r"^ST:\s*(.+?)\s*$", text, re.M | re.I)
        if not found:
            continue
        for reply in search_replies(found.group(1)):
            sock.sendto(reply, addr)
    sock.close()


def announcer(stop: threading.Event) -> None:
    while not stop.is_set():
        notify("alive")
        stop.wait(MAX_AGE // 3)


def watcher(renderer: Renderer, stop: threading.Event) -> None:
    """Notice playback ending on its own, so senders see it stop."""
    while not stop.wait(1.0):
        renderer.refresh()


def main() -> None:
    logging.basicConfig(level=os.environ.get("FREETVOS_LOG", "INFO"),
                        format="%(levelname)s %(name)s: %(message)s")
    renderer = Renderer(Player())
    subscriptions = Subscriptions()
    renderer.listeners.append(subscriptions.notify)
    server = Server(("", HTTP_PORT), make_handler(renderer, subscriptions))
    stop = threading.Event()
    for target, args in ((server.serve_forever, ()), (ssdp_responder, (stop,)),
                         (announcer, (stop,)), (watcher, (renderer, stop))):
        threading.Thread(target=target, args=args, daemon=True).start()
    log.info("renderer %s at %s", FRIENDLY_NAME, location())

    def shutdown(*_):
        stop.set()
        notify("byebye")
        renderer.player.stop()
        server.shutdown()

    signal.signal(signal.SIGTERM, shutdown)
    signal.signal(signal.SIGINT, shutdown)
    stop.wait()


if __name__ == "__main__":
    main()
