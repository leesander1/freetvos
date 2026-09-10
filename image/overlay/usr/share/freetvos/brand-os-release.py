#!/usr/bin/env python3
"""Rebrand os-release at image build time.

GRUB menu entries, the About screen and several toolkits read this file, so it
is the single cheapest branding change with the widest reach.

ID stays "fedora" on purpose. Package installs, repository definitions and
third-party installers key off it, and changing it breaks dnf. The distinct
identity goes in ID_LIKE, VARIANT and the display names, which is what the
os-release specification intends for a derivative.
"""
import os
from pathlib import Path

TARGET = Path("/usr/lib/os-release")

NAME = os.environ.get("BRAND_NAME", "FreeTVOS")
VERSION = os.environ.get("BRAND_VERSION", "0.1.0")
ID = os.environ.get("BRAND_ID", "freetvos")


def main() -> None:
    original = {}
    for line in TARGET.read_text().splitlines():
        if "=" in line and not line.startswith("#"):
            k, _, v = line.partition("=")
            original[k] = v.strip('"')

    fedora_version = original.get("VERSION_ID", "")

    out = {
        "NAME": NAME,
        "ID": "fedora",
        "ID_LIKE": "fedora",
        "VERSION": f"{VERSION} (Fedora {fedora_version})",
        "VERSION_ID": fedora_version,
        "PRETTY_NAME": f"{NAME} {VERSION}",
        "VARIANT": "Television",
        "VARIANT_ID": ID,
        "LOGO": ID,
        "ANSI_COLOR": "0;38;2;61;220;151",
        "DEFAULT_HOSTNAME": ID,
    }

    # Carried over from the base rather than rewritten. CPE_NAME identifies the
    # underlying platform to security scanners, and it is genuinely still
    # Fedora, so claiming otherwise would make vulnerability matching wrong.
    # The support and documentation links stay pointed at Fedora for the same
    # reason: that is where the answers actually are.
    for key in ("CPE_NAME", "PLATFORM_ID", "DOCUMENTATION_URL", "SUPPORT_URL",
                "BUG_REPORT_URL", "REDHAT_BUGZILLA_PRODUCT",
                "REDHAT_BUGZILLA_PRODUCT_VERSION", "REDHAT_SUPPORT_PRODUCT",
                "REDHAT_SUPPORT_PRODUCT_VERSION"):
        if original.get(key):
            out[key] = original[key]

    lines = [f'{k}="{v}"' for k, v in out.items() if v]
    TARGET.write_text("\n".join(lines) + "\n")
    print(f"os-release rebranded as {NAME} {VERSION} on Fedora {fedora_version}")


if __name__ == "__main__":
    main()
