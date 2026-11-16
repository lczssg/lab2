"""Run the seven Week 6 lab parts in the course image (part 7 on Docker host)."""
import subprocess
import time

from mininet.net import Mininet
from mininet.nodelib import LinuxBridge
from mininet.topo import SingleSwitchTopo

from verify_week6 import capture, ping, run


def shell(command):
    print("$ " + command, flush=True)
    subprocess.run(command, shell=True, check=True)


def namespaces():
    for name, suffix in (("red", 1), ("blue", 2)):
        shell(f"ip netns add {name}")
        shell(f"ip link add veth-{name} type veth peer name {name}-br")
        shell(f"ip link set veth-{name} netns {name}")
        shell(f"ip -n {name} addr add 10.1.9.{suffix}/24 dev veth-{name}")
        shell(f"ip -n {name} link set veth-{name} up")
    shell("ip link add br0 type bridge")
    shell("ip link set br0 up")
    for name in ("red", "blue"):
        shell(f"ip link set {name}-br master br0")
        shell(f"ip link set {name}-br up")
    shell("ip netns exec red ping -c 2 -W 1 10.1.9.2")
    shell("bridge fdb show br br0")
    for name in ("red", "blue"):
        shell(f"ip netns del {name}")
    shell("ip link del br0")


def network():
    return Mininet(topo=SingleSwitchTopo(k=2), controller=None,
                   switch=LinuxBridge, autoSetMacs=True, ipBase="10.1.0.0/24")


def tcp(h1, target, expected=None):
    return run(h1, f"timeout 12 iperf3 -c {target} -t 5", expected)


def main():
    print("== Part 1: Mininet hosts, namespace PIDs and veth peers")
    net = network()
    try:
        net.start()
        for h in net.hosts:
            print(h.name, "Mininet shell PID", h.pid)
            run(h, "ip -br link", 0)
        shell("lsns -t net -o NS,PID,COMMAND")
        shell("ip -br link")
    finally:
        net.stop()

    print("== Part 2: manual namespaces, veth and bridge")
    namespaces()

    net = network()
    try:
        net.start()
        h1, h2 = net["h1"], net["h2"]
        print("== Parts 3 and 4: IPv4 underlay and VXLAN")
        for local, peer in ((h1, h2), (h2, h1)):
            run(local, f"ip link add vxlan100 type vxlan id 100 local {local.IP()} remote {peer.IP()} "
                f"dstport 4789 dev {local.name}-eth0", 0)
            run(local, f"ip addr add 10.1.100.{local.name[-1]}/24 dev vxlan100", 0)
            run(local, "ip link set vxlan100 up", 0)
        with capture(h2, "h2-eth0", "udp port 4789") as trace:
            run(h1, "ping -c 2 -W 1 10.1.100.2", 0)
        assert "vni 100" in trace[0]
        run(h1, "ip -br link", 0)
        ping(h1, 1472, 0, "10.1.0.2")
        ping(h1, 1473, 1, "10.1.0.2")
        ping(h1, 1422, 0, "10.1.100.2")
        ping(h1, 1423, 1, "10.1.100.2")
        run(h2, "iperf3 -s -D", 0)
        time.sleep(.3)
        tcp(h1, "10.1.0.2", 0)
        tcp(h1, "10.1.100.2", 0)

        print("== Part 5: IPv6 underlay with an IPv4 overlay")
        for h in (h1, h2):
            run(h, f"ip -6 addr add fd00:6101::{h.name[-1]}/64 dev {h.name}-eth0", 0)
        time.sleep(1.5)
        run(h1, "ping -6 -c 2 -W 1 fd00:6101::2", 0)
        for local, peer in ((h1, h2), (h2, h1)):
            run(local, f"ip link add vxlan106 type vxlan id 106 local fd00:6101::{local.name[-1]} "
                f"remote fd00:6101::{peer.name[-1]} dstport 4789 dev {local.name}-eth0", 0)
            run(local, f"ip addr add 10.1.106.{local.name[-1]}/24 dev vxlan106", 0)
            run(local, "ip link set vxlan106 up", 0)
        with capture(h2, "h2-eth0", "ip6 and udp port 4789") as trace:
            ping(h1, 1402, 0, "10.1.106.2")
            ping(h1, 1403, 1, "10.1.106.2")
        assert "vni 106" in trace[0]
        run(h1, "ip -d link show dev vxlan106", 0)

        print("== Part 6: lower only the receiving underlay MTU")
        run(h2, "ip link set h2-eth0 mtu 1400", 0)
        ping(h1, 56, 0, "10.1.100.2")
        counters = ((net["s1"], "s1-eth2", "tx_dropped"), (h2, "h2-eth0", "rx_dropped"))
        for n, i, stat in counters:
            run(n, f"cat /sys/class/net/{i}/statistics/{stat}", 0)
        ping(h1, 1400, 1, "10.1.100.2")
        for n, i, stat in counters:
            run(n, f"cat /sys/class/net/{i}/statistics/{stat}", 0)
        tcp(h1, "10.1.100.2")
        low, high = 56, 1400
        while high - low > 1:
            size = (low + high) // 2
            if ping(h1, size, target="10.1.100.2"):
                high = size
            else:
                low = size
        print(f"== measured mismatch boundary: {low} passes, {high} fails")
        ping(h1, low, 0, "10.1.100.2")
        ping(h1, high, 1, "10.1.100.2")
        run(h1, "ip link set vxlan100 mtu 1500", 2)
        run(h2, "ip link set h2-eth0 mtu 1500", 0)
        ping(h1, 1400, 0, "10.1.100.2")
        tcp(h1, "10.1.100.2", 0)
    finally:
        net.stop()


if __name__ == "__main__":
    main()
