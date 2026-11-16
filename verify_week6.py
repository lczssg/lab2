"""Run D4/D5 in a disposable course container and save command output."""
from contextlib import contextmanager, redirect_stdout
from pathlib import Path
import subprocess
import sys
import time

from build_overlay import build, check_mtu, check_spec, load, plan

OUT = Path("evidence6")
DEST = "10.1.61.11"


@contextmanager
def topology(design, log, force=False, mode="w"):
    spec = load(design)
    assert not check_spec(spec)
    assert bool(check_mtu(spec)) == force
    with (OUT / log).open(mode, encoding="utf-8", buffering=1) as output:
        with redirect_stdout(output):
            print(f"== {design} (fresh network)")
            if force:
                print("Forced diagnostic build:", "; ".join(check_mtu(spec)))
            net, _ = build(spec)
            try:
                yield net, plan(spec)["vms"]
            finally:
                net.stop()


def run(host, command, expected=None):
    print(f"$ {host.name} {command}")
    out, err, rc = host.pexec(["sh", "-c", command])
    print(out + err, end="" if (out + err).endswith("\n") else "\n")
    print(f"[exit {rc}]")
    if expected is not None:
        assert rc == expected, (host.name, command, rc)
    return out + err, rc


@contextmanager
def capture(host, intf, filt):
    command = f"timeout -s INT 4 tcpdump -l -nnei {intf} {filt}"
    print(f"$ {host.name} {command} [capture started before probe]")
    proc = host.popen(["sh", "-c", command], stdout=subprocess.PIPE,
                      stderr=subprocess.STDOUT, text=True)
    result = []
    try:
        ready = proc.stdout.readline()
        print(ready, end="")
        while ready and "listening on" not in ready:
            ready = proc.stdout.readline()
            print(ready, end="")
        assert "listening on" in ready, "tcpdump did not start"
        yield result
    finally:
        remainder, _ = proc.communicate(timeout=8)
        print(remainder, end="")
        result.append(remainder)


def ping(host, size, expected=None, target=DEST):
    return run(host, f"ping -M do -c 1 -W 1 -s {size} {target}", expected)[1]


def tcp(net, expected=None):
    run(net["replica"], "iperf3 -s -D", 0)
    time.sleep(.3)
    return run(net["catalog"], f"timeout 15 iperf3 -c {DEST} -t 5", expected)


def main():
    OUT.mkdir(exist_ok=True)
    cmd = [sys.executable, "build_overlay.py", "blackhole.yaml"]
    rejected = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    (OUT / "check.txt").write_text("$ python3 build_overlay.py blackhole.yaml\n"
                                 + rejected.stdout + f"[exit {rejected.returncode}]\n", encoding="utf-8")
    assert rejected.returncode == 1 and rejected.stdout.count("PROBLEM:") == 2
    assert "nothing was built" in rejected.stdout

    with topology("overlay.yaml", "flood.txt") as (net, vms):
        print("== quay before the first probe")
        before, _ = run(net["quay"], "bridge fdb show dev vxlan6101", 0)
        flood = [row for row in before.splitlines() if row.startswith("00:00:00:00:00:00")]
        assert len(flood) == 2 and all("self permanent" in row for row in flood)
        assert all(v["mac"] not in before for v in vms.values())
        print("== off-path capture on vale during the first ARP/ICMP exchange")
        with capture(net["vale"], "vale-eth0", "udp port 4789") as trace:
            run(net["catalog"], f"ping -c 2 -W 1 {DEST}", 0)
        assert "vni 6101" in trace[0] and "ARP" in trace[0]
        print("== VTEP FDBs after the probe")
        for host, vm in (("quay", "replica"), ("ridge", "catalog"), ("vale", "catalog")):
            after, _ = run(net[host], "bridge fdb show dev vxlan6101", 0)
            assert vms[vm]["mac"] in after
        with (OUT / "isolation.txt").open("w", encoding="utf-8", buffering=1) as output:
            with redirect_stdout(output):
                print("== ridge hosts replica (Aster) and archive (Birch), both at " + DEST)
                run(net["catalog"], "ip neigh flush dev catalog-eth0", 0)
                with capture(net["archive"], "archive-eth0", "'arp or icmp'") as trace:
                    run(net["catalog"], f"ping -c 3 -W 1 {DEST}", 0)
                    neigh, _ = run(net["catalog"], f"ip neigh show {DEST}", 0)
                    assert vms["replica"]["mac"] in neigh
                assert "0 packets captured" in trace[0]
                print("== positive control on Birch; same capture point")
                with capture(net["archive"], "archive-eth0", "'arp or icmp'") as trace:
                    run(net["ingest"], f"ping -c 2 -W 1 {DEST}", 0)
                    neigh, _ = run(net["ingest"], f"ip neigh show {DEST}", 0)
                    assert vms["archive"]["mac"] in neigh
                assert "echo request" in trace[0]
                print("== every ordered same-tenant pair, including co-located VMs")
                for source, v in vms.items():
                    for target, peer in vms.items():
                        if source != target and v["tenant"] == peer["tenant"]:
                            run(net[source], f"ping -c 1 -W 1 {peer['ip']}", 0)
                            neigh, _ = run(net[source], f"ip neigh show {peer['ip']}", 0)
                            assert peer["mac"] in neigh
                print("== reverse negative control: .13 exists only in Aster")
                run(net["ingest"], "ping -c 2 -W 1 10.1.61.13", 1)
                run(net["ingest"], "ip neigh show 10.1.61.13", 0)

    with topology("blackhole.yaml", "blackhole.txt", force=True) as (net, _):
        ping(net["catalog"], 56, 0)
        ping(net["catalog"], 1472, 1)
        tcp(net)
        low, high = 56, 1472
        while high - low > 1:
            size = (low + high) // 2
            rc = ping(net["catalog"], size)
            assert rc in (0, 1)
            if rc:
                high = size
            else:
                low = size
        print(f"== repeated DF boundary: largest pass {low}; smallest failure {high}")
        for _ in range(2):
            ping(net["catalog"], low, 0)
            ping(net["catalog"], high, 1)

    for filename, limit, mode in (("mtu_a.yaml", 1422, "w"), ("mtu_b.yaml", 1472, "a")):
        with topology(filename, "fixes.txt", mode=mode) as (net, _):
            run(net["catalog"], "ip -br link show catalog-eth0", 0)
            run(net["quay"], "ip -br link show quay-eth0", 0)
            run(net["quay"], "ip -d link show dev vxlan6101", 0)
            with capture(net["ridge"], "ridge-eth0", "udp port 4789") as trace:
                ping(net["catalog"], limit, 0)
                ping(net["catalog"], limit + 1, 1)
            assert "vni 6101" in trace[0] and "echo request" in trace[0]
            tcp(net, 0)


if __name__ == "__main__":
    main()
