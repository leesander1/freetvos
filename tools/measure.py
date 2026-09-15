#!/usr/bin/env python3
"""How much memory and CPU the television uses, measured on the running VM.

For one moment it records memory in use and available, swap, load, CPU busy
over a short sample, and each group of processes' real memory. Real memory is
the proportional set size from /proc, which splits shared libraries fairly
between the processes sharing them; adding up plain resident sizes counts the
Qt and Chromium libraries once per process and overstates everything.

  python3 tools/measure.py "idle home screen"

Prints one line of JSON. Needs the VM running (make run).
"""
import base64
import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

SCRIPT = r'''
import json, os, re, time
from collections import defaultdict

def meminfo():
    out = {}
    for line in open("/proc/meminfo"):
        k, v = line.split(":", 1)
        out[k] = int(v.split()[0]) // 1024
    return out

def cpu_times():
    parts = open("/proc/stat").readline().split()[1:]
    vals = list(map(int, parts))
    idle = vals[3] + vals[4]
    return idle, sum(vals)

GROUPS = [
    ("chromium", r"chromium"),
    ("plasma shell", r"plasmashell"),
    ("compositor", r"kwin_wayland|Xwayland"),
    ("players", r"\bmpv\b"),
    ("bars overlay", r"qt6/bin/qml"),
    ("tvheadend", r"tvheadend"),
    ("freetvos services", r"python3 /usr/bin/freetvos-|freetvos-bars|freetvos-dial"),
    ("audio", r"pipewire|wireplumber"),
]

i1, t1 = cpu_times()
time.sleep(5)
i2, t2 = cpu_times()
busy = 100.0 * (1 - (i2 - i1) / max(1, t2 - t1))

pss = defaultdict(int)
for pid in os.listdir("/proc"):
    if not pid.isdigit():
        continue
    try:
        cmd = open(f"/proc/{pid}/cmdline", "rb").read().replace(b"\0", b" ").decode(errors="replace")
        rollup = open(f"/proc/{pid}/smaps_rollup").read()
    except OSError:
        continue
    m = re.search(r"^Pss:\s+(\d+)", rollup, re.M)
    if not m or not cmd:
        continue
    group = next((g for g, pat in GROUPS if re.search(pat, cmd)), "everything else")
    pss[group] += int(m.group(1)) // 1024

mem = meminfo()
print(json.dumps({
    "total_mb": mem["MemTotal"],
    "used_mb": mem["MemTotal"] - mem["MemAvailable"],
    "available_mb": mem["MemAvailable"],
    "swap_used_mb": mem["SwapTotal"] - mem["SwapFree"],
    "cpu_busy_pct": round(busy, 1),
    "load_1m": float(open("/proc/loadavg").read().split()[0]),
    "pss_mb": dict(sorted(pss.items(), key=lambda kv: -kv[1])),
}))
'''


def main() -> int:
    label = sys.argv[1] if len(sys.argv) > 1 else "sample"
    # Carried inside the command rather than piped in: the VM helper runs ssh
    # with standard input closed, so a piped script would never arrive.
    encoded = base64.b64encode(SCRIPT.encode()).decode()
    done = subprocess.run([str(REPO / "tools/vmssh.sh"),
                           f"echo {encoded} | base64 -d | python3 -"],
                          capture_output=True, text=True, timeout=60)
    if done.returncode != 0:
        print(done.stderr.strip(), file=sys.stderr)
        return 1
    result = json.loads(done.stdout.strip().splitlines()[-1])
    result["scenario"] = label
    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    sys.exit(main())
