#!/usr/bin/env python3
"""Extract one member from a .deb, using only the standard library.

A .deb is an ar archive holding a data tarball. Fedora ships neither dpkg-deb
nor bsdtar, and pulling in binutils just to run `ar` once during an optional
install would put a toolchain on every television. The ar format is a magic
string followed by fixed 60-byte headers, so reading it directly is shorter
than the dependency would be.
"""
import sys
import tarfile
import tempfile
from pathlib import Path

AR_MAGIC = b"!<arch>\n"


def ar_members(path: Path):
    with path.open("rb") as f:
        if f.read(8) != AR_MAGIC:
            raise SystemExit(f"{path} is not an ar archive")
        while True:
            header = f.read(60)
            if len(header) < 60:
                return
            name = header[0:16].decode("ascii", "replace").strip()
            size = int(header[48:58].decode("ascii", "replace").strip() or 0)
            data = f.read(size)
            if size % 2:            # members are padded to even offsets
                f.read(1)
            yield name.rstrip("/"), data


def main() -> int:
    deb, wanted, outdir = Path(sys.argv[1]), sys.argv[2], Path(sys.argv[3])
    outdir.mkdir(parents=True, exist_ok=True)

    for name, data in ar_members(deb):
        if not name.startswith("data.tar"):
            continue
        with tempfile.NamedTemporaryFile(suffix=name) as tmp:
            tmp.write(data)
            tmp.flush()
            # Mode "r:*" lets tarfile work out the compression, which varies
            # between .deb builds (xz today, zstd on some).
            with tarfile.open(tmp.name, "r:*") as tar:
                for member in tar.getmembers():
                    # Compare the basename exactly. endswith() also matches
                    # anything merely ending in the same characters, which a
                    # test caught: it happily picked up a "._libwidevinecdm.so"
                    # resource-fork stub instead of the library.
                    if member.isfile() and Path(member.name).name == wanted:
                        target = outdir / Path(member.name).name
                        src = tar.extractfile(member)
                        if src is None:
                            continue
                        target.write_bytes(src.read())
                        print(target)
                        return 0
    print(f"{wanted} not found inside {deb}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
