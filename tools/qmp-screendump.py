#!/usr/bin/env python3
"""Ask a running QEMU for its framebuffer over QMP."""
import json
import socket
import sys


def main() -> None:
    sock_path, out_path = sys.argv[1], sys.argv[2]
    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    s.connect(sock_path)
    f = s.makefile("rw")

    def cmd(payload: dict) -> dict:
        f.write(json.dumps(payload) + "\n")
        f.flush()
        while True:
            line = f.readline()
            if not line:
                raise SystemExit("QMP closed the connection")
            msg = json.loads(line)
            # Async notifications interleave with replies; skip them.
            if "event" in msg:
                continue
            return msg

    f.readline()  # greeting banner
    cmd({"execute": "qmp_capabilities"})
    reply = cmd({"execute": "screendump", "arguments": {"filename": out_path}})
    if "error" in reply:
        raise SystemExit(f"screendump failed: {reply['error']}")
    print(f"captured {out_path}")


if __name__ == "__main__":
    main()
