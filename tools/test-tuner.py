#!/usr/bin/env python3
"""Check the tuner setup against a pretend TVHeadend, offline.

There is no tuner in the VM and none on a Mac, so the part that can go wrong
without one is pinned down here: asking for the right scan files, finding tuner
frontends in TVHeadend's hardware tree, attaching a network to the tuners of the
right kind and only those, waiting for a scan to finish, mapping what it found
to channels, and adding the tuner to Live TV. The pretend server answers the
same API paths with the same shapes TVHeadend 4.3 sent when asked in the VM.

Run with: python3 tools/test-tuner.py
"""
import http.server
import importlib.machinery
import importlib.util
import json
import os
import sys
import tempfile
import threading
from pathlib import Path
from urllib.parse import parse_qs, urlparse

sys.dont_write_bytecode = True

REPO = Path(__file__).resolve().parent.parent
failures = []


def check(label, got, want):
    if got == want:
        print(f"  ok   {label}")
    else:
        print(f"  FAIL {label}\n         got  {got!r}\n         want {want!r}")
        failures.append(label)


class Pretend:
    """TVHeadend's state, and the requests made of it."""

    def __init__(self):
        self.requests = []
        self.networks = {}
        self.saved = []
        self.mapped = []
        self.scan_polls = 0
        self.polls_since_map = 0
        self.frontend_networks = {"fe-atsc": ["existing-net"], "fe-dvbt": []}

    def answer(self, path, params):
        self.requests.append((path, params))
        if path == "serverinfo":
            return {"sw_version": "4.3", "api_version": 19}
        if path == "dvb/scanfile/list":
            if params.get("type") == "atsc-t":
                return {"entries": [
                    {"key": "atsc-t/us/atsc-t_us-ATSC-center-frequencies-8VSB",
                     "val": "United States: us-ATSC-center-frequencies-8VSB"},
                    {"key": "atsc-t/ca/atsc-t_ca-ON-Toronto",
                     "val": "Canada: ca-ON-Toronto"}]}
            return {"entries": []}
        if path == "hardware/tree":
            tree = {
                "root": [{"uuid": "adapter0", "text": "Hauppauge #0", "class": "linuxdvb_adapter"}],
                "adapter0": [
                    {"uuid": "fe-atsc", "text": "LG LGDT3306A : ATSC #0",
                     "class": "linuxdvb_frontend_atsc_t", "leaf": True},
                    {"uuid": "fe-dvbt", "text": "Si2168 : DVB-T #1",
                     "class": "linuxdvb_frontend_dvbt", "leaf": True}],
            }
            return tree.get(params.get("uuid"), [])
        if path == "idnode/load":
            return {"entries": [{"params": [
                {"id": "networks", "value": self.frontend_networks.get(params["uuid"], [])}]}]}
        if path == "idnode/save":
            self.saved.append(json.loads(params["node"]))
            return {}
        if path == "mpegts/network/create":
            uuid = f"net{len(self.networks) + 1}"
            self.networks[uuid] = {"class": params["class"], "conf": json.loads(params["conf"])}
            return {"uuid": uuid}
        if path == "mpegts/network/scan":
            return {}
        if path == "mpegts/mux/grid":
            # Pending, then scanning, then done: the order a real scan reports.
            self.scan_polls += 1
            state = 1 if self.scan_polls == 1 else 3 if self.scan_polls == 2 else 0
            return {"entries": [{"network_uuid": uuid, "scan_state": state, "scan_result": 1}
                                for uuid in self.networks for _ in range(2)]}
        if path == "mpegts/network/grid":
            done = self.scan_polls >= 3
            # Channels appear a couple of asks after mapping, as TVHeadend's did.
            if self.mapped:
                self.polls_since_map += 1
            channels = len(self.mapped) if self.polls_since_map > 2 else 0
            return {"entries": [{"uuid": uuid, "networkname": n["conf"]["networkname"],
                                 "num_mux": 2, "num_svc": 4 if done else 1,
                                 "num_chn": channels, "scanq_length": 0 if done else 2}
                                for uuid, n in self.networks.items()]}
        if path == "mpegts/service/grid":
            # Named by network, as TVHeadend's services are, and one belonging
            # to a network set up earlier, which a scan must leave alone.
            names = {uuid: n["conf"]["networkname"] for uuid, n in self.networks.items()}
            return {"entries": [{"uuid": f"svc{i}", "network": names[uuid]}
                                for uuid in self.networks for i in range(4)]
                    + [{"uuid": "svc-other", "network": "Cable (set up earlier)"}]}
        if path == "service/mapper/save":
            self.mapped = json.loads(params["node"])["services"]
            return {}
        return None


def serve(pretend):
    class Handler(http.server.BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def handle_any(self, params):
            path = urlparse(self.path).path.removeprefix("/api/")
            reply = pretend.answer(path, params)
            if reply is None:
                self.send_response(404)
                self.end_headers()
                return
            body = json.dumps(reply).encode()
            self.send_response(200)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            self.handle_any({k: v[0] for k, v in parse_qs(urlparse(self.path).query).items()})

        def do_POST(self):
            n = int(self.headers.get("Content-Length") or 0)
            self.handle_any({k: v[0] for k, v in parse_qs(self.rfile.read(n).decode()).items()})

    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


def main() -> int:
    pretend = Pretend()
    server = serve(pretend)
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        systemctl = root / "systemctl"
        systemctl.write_text(f"#!/bin/sh\necho \"$@\" >> {root}/systemctl.log\n")
        systemctl.chmod(0o755)
        dev = root / "dev/dvb/adapter0"
        dev.mkdir(parents=True)
        (dev / "frontend0").write_text("")
        os.environ.update(
            FREETVOS_TVH=f"http://127.0.0.1:{server.server_address[1]}",
            FREETVOS_TUNER_MARKER=str(root / "state/tuner-enabled"),
            FREETVOS_TUNER_DEV=str(root / "dev/dvb"),
            FREETVOS_TUNER_PROGRESS=str(root / "run/tuner-scan.json"),
            FREETVOS_SYSTEMCTL=str(systemctl),
            FREETVOS_LIVETV_CONF=str(root / "livetv.json"),
            FREETVOS_LIVETV_CACHE=str(root / "livetv-cache"),
            FREETVOS_LIVETV_CMD=str(REPO / "image/overlay/usr/bin/freetvos-livetv"),
        )
        sys.path.insert(0, str(REPO / "image/overlay/usr/share/freetvos/livetv"))
        loader = importlib.machinery.SourceFileLoader(
            "freetvos_tuner", str(REPO / "image/overlay/usr/bin/freetvos-tuner"))
        spec = importlib.util.spec_from_loader(loader.name, loader)
        tuner = importlib.util.module_from_spec(spec)
        loader.exec_module(tuner)

        print("the option")
        check("off to begin with", tuner.enabled(), False)
        tuner.set_enabled(True, wait=5)
        check("on, and remembered for boot", tuner.enabled(), True)
        tuner.set_enabled(False)
        check("off again", tuner.enabled(), False)
        check("the service was started and stopped, and nothing else",
              (root / "systemctl.log").read_text().split("\n")[:2],
              ["start tvheadend.service", "stop tvheadend.service"])

        print("what is plugged in")
        check("a tuner the kernel sees", tuner.tuners_present(), ["adapter0/frontend0"])
        found = tuner.frontends()
        check("frontends found in the hardware tree",
              [(f["uuid"], f["class"]) for f in found],
              [("fe-atsc", "linuxdvb_frontend_atsc_t"), ("fe-dvbt", "linuxdvb_frontend_dvbt")])

        print("regions")
        places = tuner.regions("atsc-t")
        check("sorted by country, with the code taken off the place",
              [(r["country"], r["place"]) for r in places],
              [("Canada", "ON-Toronto"), ("United States", "ATSC-center-frequencies-8VSB")])
        try:
            tuner.regions("satellite")
            check("an unknown standard is refused", "accepted", "refused")
        except tuner.TunerError:
            check("an unknown standard is refused", "refused", "refused")

        print("a scan")
        result = tuner.scan("atsc-t", "atsc-t/us/atsc-t_us-ATSC-center-frequencies-8VSB",
                            poll=0.01)
        net = next(iter(pretend.networks.values()))
        check("an antenna network with the chosen frequencies",
              (net["class"], net["conf"]["scanfile"]),
              ("dvb_network_atsc_t", "atsc-t/us/atsc-t_us-ATSC-center-frequencies-8VSB"))
        check("only the antenna tuner is attached", [s["uuid"] for s in pretend.saved], ["fe-atsc"])
        check("its existing networks are kept",
              pretend.saved[0]["networks"], ["existing-net", "net1"])
        check("it waited for the scan to finish", pretend.scan_polls >= 3, True)
        check("everything found on this network became a channel, and nothing else",
              pretend.mapped, ["svc0", "svc1", "svc2", "svc3"])
        check("the result says so", (result["state"], result["services"]), ("done", 4))
        check("and counts the channels once they exist, not before",
              result["channels"], 4)
        check("progress is left for the page to read",
              json.loads(Path(os.environ["FREETVOS_TUNER_PROGRESS"]).read_text())["state"], "done")
        sources = json.loads((root / "livetv.json").read_text())["sources"]
        check("the tuner is in Live TV",
              [(s["label"], s["playlist"].endswith("/playlist/channels.m3u")) for s in sources],
              [("Tuner in this box", True)])

        print("when it cannot")
        pretend.frontend_networks = {}
        try:
            tuner.scan("dvbc", "dvbc/de/dvb-c_de-Berlin", poll=0.01)
            check("no cable tuner means no scan", "scanned", "refused")
        except tuner.TunerError as exc:
            check("no cable tuner means no scan", str(exc), "no tuner of that kind is plugged in")
        check("and the page is told why",
              json.loads(Path(os.environ["FREETVOS_TUNER_PROGRESS"]).read_text())["state"], "failed")
    server.shutdown()

    print()
    if failures:
        print(f"{len(failures)} check(s) failed")
        return 1
    print("all checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
