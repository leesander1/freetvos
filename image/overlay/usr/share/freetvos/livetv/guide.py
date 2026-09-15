"""Channels and what is on them, from whatever serves live TV on the network.

Two ways in cover nearly everything. An M3U playlist with an XMLTV guide is what
Tunarr, ErsatzTV, TVHeadend, Threadfin and every IPTV service publish. An
HDHomeRun lineup is what a real SiliconDust tuner answers, and Tunarr and
TVHeadend can pretend to be one too. Both end as the same list of channels.

Nothing here tunes anything or draws anything. It reads, matches the guide to
the channels, and answers what is on now, which is what lets it be tested
against saved replies with no tuner in sight.
"""
import datetime as dt
import json
import re
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

TIMEOUT = 20


class GuideError(Exception):
    pass


def _get(url: str) -> bytes:
    try:
        with urllib.request.urlopen(url, timeout=TIMEOUT) as response:
            return response.read()
    except (urllib.error.URLError, OSError) as exc:
        raise GuideError(f"could not reach {urllib.parse.urlparse(url).netloc}: "
                         f"{exc}") from exc


# ---------------------------------------------------------------------------
# M3U.
# ---------------------------------------------------------------------------

_ATTR = re.compile(r'([A-Za-z0-9_-]+)="([^"]*)"')


def _split_extinf(line: str) -> tuple:
    """The attributes and the display name of one #EXTINF line.

    The name is everything after the first comma that is outside the quoted
    attributes. Splitting on the first comma instead cuts "Movie Night,
    Classics" in half, and channel names with commas are ordinary.
    """
    body = line[len("#EXTINF:"):]
    in_quotes = False
    for i, char in enumerate(body):
        if char == '"':
            in_quotes = not in_quotes
        elif char == "," and not in_quotes:
            return dict(_ATTR.findall(body[:i])), body[i + 1:].strip()
    return dict(_ATTR.findall(body)), ""


def parse_m3u(text: str) -> dict:
    """{"guide": url or "", "channels": [...]} from a playlist."""
    lines = [l.strip() for l in text.replace("\r", "").split("\n")]
    if not lines or not lines[0].startswith("#EXTM3U"):
        raise GuideError("that address is not an M3U playlist")
    header = dict(_ATTR.findall(lines[0]))
    guide = header.get("url-tvg") or header.get("x-tvg-url") or ""
    channels, pending = [], None
    for line in lines[1:]:
        if line.startswith("#EXTINF:"):
            pending = _split_extinf(line)
        elif line and not line.startswith("#") and pending is not None:
            attrs, name = pending
            channels.append({
                "number": attrs.get("tvg-chno", ""),
                "name": name or attrs.get("tvg-name", ""),
                "guide_id": attrs.get("tvg-id") or attrs.get("channel-id", ""),
                "logo": attrs.get("tvg-logo", ""),
                "group": attrs.get("group-title", ""),
                "url": line,
            })
            pending = None
    return {"guide": guide.split(",")[0].strip(), "channels": channels}


# ---------------------------------------------------------------------------
# HDHomeRun.
# ---------------------------------------------------------------------------


def parse_lineup(items: list) -> list:
    out = []
    for item in items or []:
        if not item.get("URL"):
            continue
        out.append({"number": str(item.get("GuideNumber", "")),
                    "name": item.get("GuideName", ""),
                    "guide_id": "", "logo": "", "group": "",
                    "url": item["URL"]})
    return out


def hdhomerun(base: str) -> dict:
    """A tuner or anything pretending to be one, from its address."""
    base = normalise_address(base, default_port=80)
    try:
        info = json.loads(_get(f"{base}/discover.json"))
    except ValueError as exc:
        raise GuideError("that address did not answer like an HDHomeRun") from exc
    lineup_url = info.get("LineupURL") or f"{base}/lineup.json"
    try:
        channels = parse_lineup(json.loads(_get(lineup_url)))
    except ValueError as exc:
        raise GuideError("the tuner's channel list was unreadable") from exc
    return {"name": info.get("FriendlyName", "HDHomeRun"),
            "channels": channels}


# ---------------------------------------------------------------------------
# XMLTV.
# ---------------------------------------------------------------------------


def parse_xmltv_time(value: str):
    """XMLTV's "20260915180000 +0000", as an aware datetime.

    The offset is part of the value and is not always UTC. Reading the digits
    alone and assuming UTC shifts every programme from a guide written in local
    time by the width of the time zone.
    """
    m = re.match(r"^\s*(\d{14})\s*([+-]\d{4})?", value or "")
    if not m:
        return None
    moment = dt.datetime.strptime(m.group(1), "%Y%m%d%H%M%S")
    offset = m.group(2) or "+0000"
    sign = 1 if offset[0] == "+" else -1
    delta = dt.timedelta(hours=int(offset[1:3]), minutes=int(offset[3:5]))
    return moment.replace(tzinfo=dt.timezone(sign * delta))


def parse_xmltv(raw: bytes) -> dict:
    """{"channels": {id: [display names]}, "programmes": {id: [shows]}}"""
    try:
        root = ET.fromstring(raw)
    except ET.ParseError as exc:
        raise GuideError("that address is not an XMLTV guide") from exc
    channels = {}
    for element in root.findall("channel"):
        names = [(n.text or "").strip() for n in element.findall("display-name")]
        channels[element.get("id", "")] = [n for n in names if n]
    programmes: dict = {}
    for element in root.findall("programme"):
        start = parse_xmltv_time(element.get("start", ""))
        stop = parse_xmltv_time(element.get("stop", ""))
        if start is None:
            continue
        programmes.setdefault(element.get("channel", ""), []).append({
            "title": (element.findtext("title") or "").strip(),
            "subtitle": (element.findtext("sub-title") or "").strip(),
            "description": (element.findtext("desc") or "").strip(),
            "episode": (element.findtext("episode-num") or "").strip(),
            "start": start,
            "stop": stop,
        })
    for shows in programmes.values():
        shows.sort(key=lambda s: s["start"])
    # A show with no stop time runs until the next one starts.
    for shows in programmes.values():
        for i, show in enumerate(shows):
            if show["stop"] is None:
                show["stop"] = (shows[i + 1]["start"] if i + 1 < len(shows)
                                else show["start"] + dt.timedelta(hours=1))
    return {"channels": channels, "programmes": programmes}


def match_guide(channels: list, guide: dict) -> dict:
    """Which guide id belongs to each channel, by position in the list.

    By the playlist's own id first, which is what Tunarr and TVHeadend give.
    Failing that by channel number and then by name against the guide's
    display names, which is how a bare HDHomeRun lineup has to be matched,
    because it carries no guide ids at all.
    """
    by_name: dict = {}
    for guide_id, names in guide.get("channels", {}).items():
        for name in names:
            by_name.setdefault(name.lower(), guide_id)
    out = {}
    for index, channel in enumerate(channels):
        if channel.get("guide_id") and channel["guide_id"] in guide.get(
                "programmes", {}):
            out[index] = channel["guide_id"]
            continue
        for candidate in (channel.get("number", ""),
                          f"{channel.get('number', '')} {channel.get('name', '')}",
                          channel.get("name", "")):
            found = by_name.get(candidate.strip().lower())
            if candidate.strip() and found:
                out[index] = found
                break
    return out


def on_now(shows: list, now: dt.datetime) -> tuple:
    """(what is on, what is next), either of which may be None."""
    current = None
    for i, show in enumerate(shows or []):
        if show["start"] <= now < show["stop"]:
            current = show
            return current, (shows[i + 1] if i + 1 < len(shows) else None)
        if show["start"] > now:
            return None, show
    return None, None


def window(shows: list, start: dt.datetime, end: dt.datetime) -> list:
    """The shows overlapping a stretch of time, for drawing the guide grid."""
    return [s for s in shows or [] if s["stop"] > start and s["start"] < end]


# ---------------------------------------------------------------------------
# Addresses.
# ---------------------------------------------------------------------------


def normalise_address(address: str, default_port: int = 8000) -> str:
    """What someone types into a television, as a base URL.

    tunarr.lan becomes http://tunarr.lan:8000, which is Tunarr's own default,
    because typing a scheme and a port with a remote is the part people get
    wrong.
    """
    address = (address or "").strip().rstrip("/")
    if not address:
        return ""
    if "://" not in address:
        address = "http://" + address
    parsed = urllib.parse.urlparse(address)
    if parsed.port is None and parsed.hostname and not parsed.path.strip("/"):
        address = f"{parsed.scheme}://{parsed.hostname}:{default_port}"
    return address


def sort_channels(channels: list) -> list:
    """By channel number the way a remote counts: 2 before 10, 5.1 after 5."""
    def key(channel):
        parts = re.findall(r"\d+", channel.get("number", ""))
        return ([int(p) for p in parts] or [10 ** 9], channel.get("name", "").lower())
    return sorted(channels, key=key)
