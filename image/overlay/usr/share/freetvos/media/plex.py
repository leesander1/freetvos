"""Talking to a Plex server, and signing in without ever seeing a password.

Plex publishes a linking flow built for devices exactly like this one: the
television asks for a four-character code, shows it on screen, and the viewer
types it into plex.tv/link on a phone they are already signed in on. The
password is entered on their own device, into Plex's own page. Nothing here ever
handles it, which is the only acceptable arrangement for a box in a living room.

The token that comes back is the viewer's, is stored with their own files, and
is the only credential this holds.
"""
import json
import time
import urllib.error
import urllib.parse
import urllib.request

PLEX_TV = "https://plex.tv/api/v2"
TIMEOUT = 15


class PlexError(Exception):
    pass


def _headers(client_id: str, token: str = "") -> dict:
    head = {
        "Accept": "application/json",
        "X-Plex-Product": "FreeTVOS",
        "X-Plex-Version": "0.1.0",
        "X-Plex-Client-Identifier": client_id,
        "X-Plex-Platform": "Linux",
        "X-Plex-Device": "FreeTVOS",
        "X-Plex-Device-Name": "Television",
    }
    if token:
        head["X-Plex-Token"] = token
    return head


def _call(url: str, headers: dict, method: str = "GET", timeout=TIMEOUT):
    request = urllib.request.Request(url, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = response.read()
    except urllib.error.HTTPError as exc:
        raise PlexError(f"Plex said {exc.code}") from exc
    except (urllib.error.URLError, OSError) as exc:
        raise PlexError(f"could not reach Plex: {exc}") from exc
    if not body:
        return {}
    try:
        return json.loads(body)
    except ValueError as exc:
        raise PlexError("Plex sent something unreadable") from exc


# ---------------------------------------------------------------------------
# Signing in.
# ---------------------------------------------------------------------------


def request_pin(client_id: str) -> dict:
    """Ask for a code to show on screen. Returns its id and the code itself.

    Deliberately not a strong pin. That variant returns a twenty-five character
    string, which is right for a link or a QR code and useless to somebody
    holding a remote in front of a television: the short code is the one
    plex.tv/link asks for and the only one a person will read off a screen and
    type correctly.
    """
    data = _call(f"{PLEX_TV}/pins", _headers(client_id), "POST")
    if not data.get("code"):
        raise PlexError("Plex did not return a code")
    return {"id": data["id"], "code": data["code"]}


def poll_pin(client_id: str, pin_id) -> str:
    """The token once the viewer has entered the code, or an empty string."""
    data = _call(f"{PLEX_TV}/pins/{pin_id}", _headers(client_id))
    return data.get("authToken") or ""


def servers(client_id: str, token: str) -> list:
    """Every server this account can reach, best address first.

    Local addresses are tried before the relay. A server in the same house is
    both faster and not someone else's bandwidth, and the relay caps quality.
    """
    data = _call(f"{PLEX_TV}/resources?includeHttps=1&includeRelay=1",
                 _headers(client_id, token))
    out = []
    for resource in data if isinstance(data, list) else []:
        if "server" not in (resource.get("provides") or ""):
            continue
        connections = resource.get("connections") or []
        ordered = sorted(
            connections,
            key=lambda c: (bool(c.get("relay")), not c.get("local"),
                           not str(c.get("uri", "")).startswith("https")))
        out.append({
            "name": resource.get("name") or "Plex",
            "id": resource.get("clientIdentifier") or "",
            "token": resource.get("accessToken") or token,
            "uris": [c["uri"] for c in ordered if c.get("uri")],
            "owned": bool(resource.get("owned")),
        })
    return out


def reachable(server: dict, client_id: str, timeout: float = 4.0) -> str:
    """The first address that answers. Servers advertise several, most dead."""
    for uri in server.get("uris", []):
        try:
            _call(f"{uri}/identity", _headers(client_id, server["token"]),
                  timeout=timeout)
            return uri
        except PlexError:
            continue
    return ""


# ---------------------------------------------------------------------------
# Reading a library.
# ---------------------------------------------------------------------------


def _items(payload) -> list:
    container = (payload or {}).get("MediaContainer") or {}
    return container.get("Metadata") or container.get("Directory") or []


def libraries(base: str, token: str, client_id: str) -> list:
    data = _call(f"{base}/library/sections", _headers(client_id, token))
    return [{"key": d.get("key"), "title": d.get("title"),
             "type": d.get("type")}
            for d in _items(data) if d.get("key")]


def library_items(base: str, token: str, client_id: str, key: str) -> list:
    data = _call(f"{base}/library/sections/{key}/all?sort=titleSort",
                 _headers(client_id, token))
    return [normalise(d) for d in _items(data)]


def children(base: str, token: str, client_id: str, rating_key: str) -> list:
    data = _call(f"{base}/library/metadata/{rating_key}/children",
                 _headers(client_id, token))
    return [normalise(d) for d in _items(data)]


def on_deck(base: str, token: str, client_id: str) -> list:
    """What this account is part way through, newest first."""
    data = _call(f"{base}/library/onDeck", _headers(client_id, token))
    return [normalise(d) for d in _items(data)]


def normalise(entry: dict) -> dict:
    """One shape for everything, so the pages do not care what Plex called it."""
    kind = entry.get("type") or "item"
    playable = kind in ("movie", "episode", "track", "clip")
    offset = int(entry.get("viewOffset") or 0) // 1000
    duration = int(entry.get("duration") or 0) // 1000

    title = entry.get("title") or "Untitled"
    if kind == "episode":
        show = entry.get("grandparentTitle") or ""
        season = entry.get("parentIndex")
        number = entry.get("index")
        if show and season is not None and number is not None:
            title = f"{show} · S{season}E{number} · {title}"

    part = ""
    for medium in entry.get("Media") or []:
        for piece in medium.get("Part") or []:
            if piece.get("key"):
                part = piece["key"]
                break
        if part:
            break

    return {
        "id": str(entry.get("ratingKey") or ""),
        "title": title,
        "kind": kind,
        "playable": playable,
        "part": part,
        "offset": offset,
        "duration": duration,
        "thumb": entry.get("thumb") or entry.get("grandparentThumb") or "",
        "year": entry.get("year") or "",
    }


def stream_url(base: str, token: str, part: str) -> str:
    """The file itself, played directly rather than transcoded.

    Direct play because the box is doing the decoding anyway and a transcode
    makes the server work for nothing. Anything the player cannot decode is a
    reason to fix the player, not to push the problem up the wire.
    """
    joiner = "&" if "?" in part else "?"
    return f"{base}{part}{joiner}X-Plex-Token={urllib.parse.quote(token)}"


def image_url(base: str, token: str, thumb: str, width: int = 400) -> str:
    if not thumb:
        return ""
    inner = urllib.parse.quote(thumb, safe="")
    return (f"{base}/photo/:/transcode?width={width}&height={width}"
            f"&minSize=1&url={inner}&X-Plex-Token={urllib.parse.quote(token)}")


def wait_for_token(client_id: str, pin_id, seconds: int = 300,
                   every: float = 2.0):
    """Block until the code is entered, or give up. Used from the command line."""
    deadline = time.time() + seconds
    while time.time() < deadline:
        token = poll_pin(client_id, pin_id)
        if token:
            return token
        time.sleep(every)
    return ""
