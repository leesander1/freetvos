"""Talking to a Jellyfin server, and signing in without ever seeing a password.

Jellyfin's Quick Connect is the same shape as Plex's linking flow: the
television asks for a code, shows it on screen, and the viewer approves it from
a device already signed in. No password passes through here.

Quick Connect can be switched off by whoever runs the server, so there is a
fallback, and it is deliberately not a password box on this television: it asks
the viewer to enable Quick Connect instead. A television that collects passwords
is a television worth attacking.
"""
import json
import urllib.error
import urllib.parse
import urllib.request

TIMEOUT = 15


class JellyfinError(Exception):
    pass


def _auth_header(client_id: str, token: str = "") -> str:
    parts = [
        'MediaBrowser Client="FreeTVOS"',
        'Device="Television"',
        f'DeviceId="{client_id}"',
        'Version="0.1.0"',
    ]
    if token:
        parts.append(f'Token="{token}"')
    return ", ".join(parts)


def _call(base: str, path: str, client_id: str, token: str = "",
          method: str = "GET", body=None, timeout=TIMEOUT):
    url = f"{base.rstrip('/')}{path}"
    headers = {
        "Accept": "application/json",
        "Authorization": _auth_header(client_id, token),
    }
    data = None
    if body is not None:
        data = json.dumps(body).encode()
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(url, headers=headers, method=method,
                                     data=data)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            payload = response.read()
    except urllib.error.HTTPError as exc:
        raise JellyfinError(f"the server said {exc.code}") from exc
    except (urllib.error.URLError, OSError) as exc:
        raise JellyfinError(f"could not reach the server: {exc}") from exc
    if not payload:
        return {}
    try:
        return json.loads(payload)
    except ValueError as exc:
        raise JellyfinError("the server sent something unreadable") from exc


def normalise_address(address: str) -> str:
    """What someone types, turned into something to connect to."""
    address = (address or "").strip().rstrip("/")
    if not address:
        return ""
    if "://" not in address:
        # Plain http by default. A Jellyfin on the same network is usually
        # served over http, and guessing https makes the first attempt fail for
        # almost everyone.
        address = "http://" + address
    parsed = urllib.parse.urlparse(address)
    if not parsed.port and parsed.scheme == "http":
        address = f"{address}:8096"
    return address


def identify(base: str, client_id: str) -> dict:
    """Prove there is a Jellyfin at this address before going further."""
    info = _call(base, "/System/Info/Public", client_id, timeout=8)
    if not info.get("Id"):
        raise JellyfinError("that address did not answer like a Jellyfin server")
    return {"name": info.get("ServerName") or "Jellyfin",
            "id": info["Id"], "version": info.get("Version") or ""}


# ---------------------------------------------------------------------------
# Signing in.
# ---------------------------------------------------------------------------


def quick_connect_start(base: str, client_id: str) -> dict:
    state = _call(base, "/QuickConnect/Initiate", client_id, method="POST")
    if not state.get("Code"):
        raise JellyfinError(
            "Quick Connect is switched off on this server. Turn it on in "
            "the Jellyfin dashboard, under General, and try again.")
    return {"code": state["Code"], "secret": state["Secret"]}


def quick_connect_check(base: str, client_id: str, secret: str) -> bool:
    state = _call(base, f"/QuickConnect/Connect?secret={urllib.parse.quote(secret)}",
                  client_id)
    return bool(state.get("Authenticated"))


def quick_connect_finish(base: str, client_id: str, secret: str) -> dict:
    result = _call(base, "/Users/AuthenticateWithQuickConnect", client_id,
                   method="POST", body={"Secret": secret})
    token = result.get("AccessToken")
    user = (result.get("User") or {}).get("Id")
    if not token or not user:
        raise JellyfinError("the server did not return a sign-in")
    return {"token": token, "user": user,
            "name": (result.get("User") or {}).get("Name") or ""}


# ---------------------------------------------------------------------------
# Reading a library.
# ---------------------------------------------------------------------------

FIELDS = "Path,MediaSources,RunTimeTicks,UserData,ProductionYear"
TICKS = 10_000_000            # Jellyfin counts in hundred-nanosecond units


def views(base: str, client_id: str, token: str, user: str) -> list:
    data = _call(base, f"/Users/{user}/Views", client_id, token)
    return [{"id": v["Id"], "title": v.get("Name") or "Library",
             "kind": v.get("CollectionType") or ""}
            for v in data.get("Items") or [] if v.get("Id")]


def items(base: str, client_id: str, token: str, user: str,
          parent: str = "") -> list:
    query = {"SortBy": "SortName", "SortOrder": "Ascending",
             "Fields": FIELDS, "Limit": "400"}
    if parent:
        query["ParentId"] = parent
    data = _call(base, f"/Users/{user}/Items?{urllib.parse.urlencode(query)}",
                 client_id, token)
    return [normalise(i) for i in data.get("Items") or []]


def resume(base: str, client_id: str, token: str, user: str) -> list:
    query = {"Limit": "24", "Fields": FIELDS,
             "MediaTypes": "Video", "Recursive": "true"}
    data = _call(base, f"/Users/{user}/Items/Resume?{urllib.parse.urlencode(query)}",
                 client_id, token)
    return [normalise(i) for i in data.get("Items") or []]


def normalise(entry: dict) -> dict:
    kind = entry.get("Type") or "Item"
    playable = kind in ("Movie", "Episode", "Video", "Audio", "MusicVideo")
    user_data = entry.get("UserData") or {}

    title = entry.get("Name") or "Untitled"
    if kind == "Episode":
        show = entry.get("SeriesName") or ""
        season = entry.get("ParentIndexNumber")
        number = entry.get("IndexNumber")
        if show and season is not None and number is not None:
            title = f"{show} · S{season}E{number} · {title}"

    return {
        "id": entry.get("Id") or "",
        "title": title,
        "kind": kind,
        "playable": playable,
        "offset": int(user_data.get("PlaybackPositionTicks") or 0) // TICKS,
        "duration": int(entry.get("RunTimeTicks") or 0) // TICKS,
        "thumb": entry.get("Id") if entry.get("ImageTags") else "",
        "year": entry.get("ProductionYear") or "",
    }


def stream_url(base: str, token: str, item_id: str) -> str:
    """The file itself. Direct play, for the same reason as everywhere else."""
    return (f"{base.rstrip('/')}/Videos/{item_id}/stream?static=true"
            f"&api_key={urllib.parse.quote(token)}")


def image_url(base: str, item_id: str, width: int = 400) -> str:
    if not item_id:
        return ""
    return (f"{base.rstrip('/')}/Items/{item_id}/Images/Primary"
            f"?fillWidth={width}&quality=90")


def report_progress(base: str, client_id: str, token: str, item_id: str,
                    seconds: int) -> None:
    """Tell the server where the viewer stopped, so other devices agree.

    Best effort. A position that fails to reach the server is a small
    annoyance; an exception here would take the whole player down with it.
    """
    try:
        _call(base, "/Sessions/Playing/Stopped", client_id, token,
              method="POST",
              body={"ItemId": item_id, "PositionTicks": int(seconds) * TICKS})
    except JellyfinError:
        pass
