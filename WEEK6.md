# Week 6 — Virtualisation and VXLAN

[Published Week 6 assignment](https://lczssg.github.io/lab2/week6/) ·
[Course lab and marking rubric](https://firdaussahran.github.io/wic2005/weeks/week-06/#tab-lab) ·
[Week 6 Spectrum activity](https://spectrum.um.edu.my/mod/assign/view.php?id=1151079)

## Reproduce

From the repository directory in PowerShell, use the course's Docker image.
The Mininet containers have no external network and are removed on exit.
Run the throughput experiments one at a time.

```powershell
$repo = (Get-Location).Path
docker run --rm --network none --cap-add NET_ADMIN --cap-add SYS_ADMIN --mount "type=bind,source=$repo,target=/lab" -w /lab firdaussahran/netlab-mininet:1.0 python3 -u run_lab6.py 2>&1 | Set-Content -Encoding utf8 evidence6/lab-parts1-6.txt
docker run --rm alpine:3.20 sh -c 'ip addr show eth0; cat /etc/os-release; ps'
docker run --rm --network none --cap-add NET_ADMIN --cap-add SYS_ADMIN --mount "type=bind,source=$repo,target=/lab" -w /lab firdaussahran/netlab-mininet:1.0 python3 verify_week6.py
docker run --rm --network none --mount "type=bind,source=$repo,target=/lab" -w /lab firdaussahran/netlab-mininet:1.0 python3 make_page6.py overlay.yaml
```

For an interactive overlay, use the assignment container command with `-it` and replace `python3 verify_week6.py` with `python3 build_overlay.py overlay.yaml`. The scripts leave warnings visible; the recorded D5 tests assert the actual command exit statuses, expected MACs, packet capture contents and DF boundaries. Runtime-only link settings suppress IPv6 autoconfiguration even when the container's IPv6 sysctls are read-only. This keeps the IPv4 learning test free of startup traffic without changing the generated VTEP command list.

## Lab wrap-up

1. A Mininet host is a process in a separate network namespace, with its own interfaces and routes. The Mininet shell PIDs correspond to the Linux namespace listing. Each cable is a veth pair with one end in that namespace and the other on the switch bridge. The two manual namespaces also communicated through a Linux bridge, which learned their source MACs. See [Parts 1–6](evidence6/lab-parts1-6.txt).
2. The MTUs and adjacent payload probes were:

   | Path | IP MTU | Largest passing / first failing DF payload | TCP receiver |
   | --- | ---: | ---: | ---: |
   | Plain IPv4 underlay | 1500 | 1472 / 1473 | 26.6 Gbit/s |
   | VNI 100 over IPv4 | 1450 | 1422 / 1423 | 15.2 Gbit/s |
   | VNI 106 over IPv6 | 1430 | 1402 / 1403 | not measured |

   Every inner IPv4 echo adds 28 bytes for IPv4 and ICMP. The 50-byte IPv4 tunnel deduction within the outer IP MTU is inner Ethernet 14 + VXLAN 8 + UDP 8 + outer IPv4 20. Outer Ethernet is outside that budget. The IPv6 outer header is 40 bytes, so the tunnel deduction is 70. The IPv4-overlay receiver ran at about 57% of the plain underlay rate in these virtual tests. Encapsulation work and smaller packets matter; software rates vary with CPU and offloads and do not predict a physical link's rate.
3. With the receiver's underlay MTU reduced to 1400, 56-byte echo data still passed; 1400-byte echo data was dropped. Both tracked drop counters rose from 0 to 1 for that probe. The largest passing DF payload was 1326 and the first failing one was 1327. The former gives 1404 bytes of outer IP (1326 + 28 + 50), consistent with a four-byte receive allowance for a possible VLAN tag. TCP connected with small control packets but then dropped data at full segment sizes: the receiver got 2.93 Mbit/s during the mismatch and 19.5 Gbit/s after restoring 1500.
4. [Part 7](evidence6/lab-part7.txt) shows Alpine's `eth0@if...`, its Alpine 3.20.10 filesystem and its own PID namespace. Unlike a plain Mininet host, a Docker container has a filesystem from an image and process isolation as well as network isolation.
5. The Week 5 P4 tunnel inserted a custom four-byte header between Ethernet and IPv4. Every participating P4 switch looked up its tunnel destination and the assignment's added hop limit eventually stopped loops. VXLAN wraps the entire inner Ethernet frame in standard VXLAN/UDP/IP. Only VTEPs parse VXLAN; underlay routers forward by outer IP and decrement the outer TTL or IPv6 Hop Limit. The lab underlay's Linux bridge operates at L2, so it forwards frames without decrementing IP TTL.

## Assignment evidence and review

- [MTU rejection](evidence6/check.txt): both tenants exceed 1500 by 50 bytes; the process exits before Mininet is built.
- [Flood-and-learn](evidence6/flood.txt): compare static flood entries with learned MAC-to-VTEP entries; inspect Vale's off-path ARP capture.
- [Isolation and reachability](evidence6/isolation.txt): no Aster ARP/ICMP reached the Birch archive; the capture works in Birch's positive control. All 18 directed same-tenant pairs resolve to their own VM MACs, and Birch cannot resolve Aster-only .13.
- [Forced failure](evidence6/blackhole.txt) and [both fixes](evidence6/fixes.txt): compare timeout with local MTU rejection, Ethernet capture lengths and TCP receiver rates.
- To explain the result, separate the guest's ARP table (IP → MAC), the VTEP's FDB (MAC → remote VTEP), and the underlay's routing (outer IP). For the size evidence, derive 1422 = 1500 − 50 − 28 and explain why the first failure is silent in the forced build but local in Fix A.
