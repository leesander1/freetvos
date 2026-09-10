#!/usr/bin/env python3
"""Send key events to the running VM through QEMU's monitor.

Testing d-pad navigation needs real key events arriving the way a remote's
would, not synthetic events injected inside the guest. QMP's send-key puts them
in at the virtual keyboard, so everything above it, the compositor, the
toolkit, the web page, sees exactly what hardware would produce.

Usage: sendkey.py down down right ret
"""
import json
import socket
import sys
import time

SOCK = "output/qmp.sock"


def main() -> int:
    keys = sys.argv[1:]
    if not keys:
        print("usage: sendkey.py <qcode> [qcode...]", file=sys.stderr)
        return 2

    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    s.connect(SOCK)
    f = s.makefile("rw")

    def cmd(payload: dict) -> dict:
        f.write(json.dumps(payload) + "\n")
        f.flush()
        while True:
            line = f.readline()
            if not line:
                raise SystemExit("QMP closed the connection")
            msg = json.loads(line)
            if "event" in msg:
                continue
            return msg

    f.readline()
    cmd({"execute": "qmp_capabilities"})
    for k in keys:
        reply = cmd({"execute": "send-key", "arguments": {
            "keys": [{"type": "qcode", "data": k}]}})
        if "error" in reply:
            print(f"{k}: {reply['error']}", file=sys.stderr)
            return 1
        print(f"sent {k}")
        # A short gap so the page has time to move focus and repaint before
        # the next key lands; bursting them tests nothing.
        time.sleep(0.4)
    return 0


if __name__ == "__main__":
    sys.exit(main())
