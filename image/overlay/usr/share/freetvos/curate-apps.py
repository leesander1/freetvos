#!/usr/bin/env python3
"""Hide desktop entries that have no business on a television.

Run at image build time, not on the device. Bigscreen's model filters on
NoDisplay, so setting it in the system entry is deterministic and takes effect
on first boot with no cache rebuild and no per-user state.

Doing it at runtime instead turned out not to work: a user-level override in
~/.local/share/applications reaches the model only through the cached service
database, and the entry stayed on the grid across a full session restart.
Bigscreen's own blocklist key is stored somewhere that moved between the
version packaged here and upstream master, so it is not a stable target either.
Editing the shipped entry avoids both problems.
"""
import re
import sys
from pathlib import Path

APPS = Path("/usr/share/applications")
CONF = Path("/etc/freetvos/apps.conf")


def parse_conf(path: Path) -> tuple[set[str], set[str]]:
    """Pull the HIDE and SHOW lists out of the shell-style config."""
    text = path.read_text() if path.exists() else ""
    out = {}
    for key in ("HIDE", "SHOW"):
        m = re.search(rf'^{key}="([^"]*)"', text, re.M | re.S)
        out[key] = set(m.group(1).split()) if m else set()
    return out["HIDE"], out["SHOW"]


def main() -> int:
    hide, show = parse_conf(CONF)
    hide -= show
    if not hide:
        print("nothing to hide")
        return 0

    hidden = 0
    for entry_id in sorted(hide):
        f = APPS / f"{entry_id}.desktop"
        if not f.exists():
            print(f"  skip {entry_id}: not installed")
            continue
        lines = [l for l in f.read_text().splitlines()
                 if not l.startswith("NoDisplay=")]
        # NoDisplay belongs in the [Desktop Entry] group. Appending blindly
        # would drop it into whatever action group happens to be last, where
        # it means nothing.
        try:
            start = lines.index("[Desktop Entry]")
        except ValueError:
            print(f"  skip {entry_id}: no [Desktop Entry] group")
            continue
        end = next((i for i in range(start + 1, len(lines))
                    if lines[i].startswith("[")), len(lines))
        lines.insert(end, "NoDisplay=true")
        f.write_text("\n".join(lines) + "\n")
        print(f"  hid {entry_id}")
        hidden += 1

    print(f"hid {hidden} entries")
    return 0


if __name__ == "__main__":
    sys.exit(main())
