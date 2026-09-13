#!/usr/bin/env python3
"""Turn each .app definition into a .desktop entry at image build time.

The Bigscreen home screen builds its tile grid from installed desktop entries,
so generating them here is what makes a service appear on the TV. Doing it at
build time rather than first boot keeps /usr the only source of truth, which is
what bootc wants: the running system stays a read-only, atomically swappable
image with no generated state to drift.
"""
import shlex
from pathlib import Path

APPS = Path("/usr/share/freetvos/webapps")
OUT = Path("/usr/share/applications")


def parse(path: Path) -> dict:
    """Read the shell-style key="value" definitions without running them."""
    values = {}
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, raw = line.partition("=")
        parts = shlex.split(raw)
        values[key.strip()] = parts[0] if parts else ""
    return values


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for app_file in sorted(APPS.glob("*.app")):
        app_id = app_file.stem
        cfg = parse(app_file)
        name = cfg.get("NAME", app_id)
        entry = "\n".join([
            "[Desktop Entry]",
            "Type=Application",
            f"Name={name}",
            f"Comment={name} on FreeTVOS",
            # A service can name its own launcher. Jellyfin has no public web
            # address, so its tile needs a step that finds your server before
            # the web app can open it.
            f"Exec={cfg['LAUNCHER']}" if cfg.get("LAUNCHER")
            else f"Exec=/usr/bin/freetvos-webapp {app_id}",
            f"Icon={cfg.get('ICON', 'freetvos-' + app_id)}",
            f"Categories={cfg.get('CATEGORY', 'AudioVideo;Video;')}",
            "Terminal=false",
            "StartupNotify=true",
            # Bigscreen reads this to decide what belongs on the TV grid;
            # without it the entry is treated as an ordinary desktop app.
            "X-KDE-FormFactor=tv",
            f"X-FreeTVOS-WebApp={app_id}",
            f"X-FreeTVOS-DRM={cfg.get('DRM', 'no')}",
            "",
        ])
        target = OUT / f"freetvos-{app_id}.desktop"
        target.write_text(entry)
        print(f"generated {target}")


if __name__ == "__main__":
    main()
