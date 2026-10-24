# Week 3: routed network from data

This extends the same Week 2 repository. The original Week 2 homepage is in `docs/index.html`; the generated Week 3 page is in `docs/week3/index.html`.

## Files and design

- `network.yaml`: four routers in a ring, four LANs, and static routes within `10.1.0.0/16`.
- `build_routed.py`: validates the description and all directed host-to-host forwarding paths before building the Mininet network.
- `loop.yaml` and `missing.yaml`: deliberate faults used to test rejection before building.
- `make_page3.py`: checks the same model and generates the network, connected/static routing tables sorted by descending prefix length, evidence, and written answers.
- `page3.yaml`: repository link and four answers based on this network and its captured outputs.
- `evidence3/`: plain-text output captured from real execution.

Each router has one `/24` LAN. The router is `.1`, the host is `.10`, and inter-router links use `/30`. The `10.1.48.0/22` summary covers the h2 and h3 LANs without including the h1 or h4 LAN. r1's `10.1.50.0/24` entry overrides its summary by longest-prefix match. r4 is the clean demonstration point for the summary because both destination LANs use `10.1.34.1` there.

## Reproduce inside the isolated course Linux container

Start in the mounted repository directory, with Mininet and PyYAML installed. Building requires the container capabilities needed by Mininet. Reuse the existing isolated course setup and do not run global Docker cleanup.

```sh
# These should reject the description and exit nonzero before Mininet builds.
python3 build_routed.py loop.yaml
python3 build_routed.py missing.yaml

# The good description must pass validation before the Mininet CLI appears.
python3 build_routed.py network.yaml
```

For the complete recorded experiment, including the guided exercises, run `sh commands/run-week3.sh` inside the isolated container. It uses the CLI's supported script mode via the optional `--commands` argument; piping a file into an interactive CLI can make it consume later commands as node input. The command files preserve exactly what was executed, and the resulting session logs and individual outputs are checked by `verify_week3.py`.

The runner remounts `/proc/sys` writable only inside this disposable container's mount namespace so the supplied router classes can change network-namespace sysctls. Docker otherwise mounts it read-only, which prevents the guided forwarding toggles and IPv6 configuration. The lab needs NET_ADMIN and SYS_ADMIN; it does not use `--privileged`, host networking, the Docker socket, or any NetBox mount. Mininet reports a resource-limit warning in this environment; these results verify functional routing, not throughput or timing performance.

All lab files, custom temporary files and evidence are stored under the D: workspace. At the Mininet CLI, the following operations produce the evidence. Relative redirection paths resolve inside the mounted `/lab` repository. The command files include descriptive headings and retain expected errors from the fault experiment.

| Evidence file | Commands and observations |
| --- | --- |
| `evidence3/pingall.txt` | `py net.ping([net.get(h) for h in ('h1','h2','h3','h4')])`: all 12 directed pairs among the four LAN hosts should succeed. Plain `pingall` also includes the router nodes in this topology, so use this explicit host list. |
| `evidence3/routes.txt` | `r1 ip route`, `r2 ip route`, `r3 ip route`, `r4 ip route`, each with a router heading. |
| `evidence3/traces.txt` | `h1 traceroute -n -I -m 8 -w 1 -q 1 10.1.48.10`, then destinations `10.1.50.10` and `10.1.80.10`. |
| `evidence3/summary.txt` | `r4 ip route get 10.1.48.10` and `r4 ip route get 10.1.50.10`; both should use `10.1.34.1`. |
| `evidence3/failure.txt` | Record a working h1-to-h3 baseline; `link r1 r4 down`; rerun the bounded h1-to-h3 traceroute and `r1 ip route get 10.1.50.10`; `link r1 r4 up`; verify h1-to-h3 recovery and repeat the explicit four-host ping command above. |
| `evidence3/check.txt` | The exact loop/missing-route rejection output; the runner requires both commands to exit nonzero. `model-check.txt` records the good-model assertions. |

The measured link-down behaviour is important: Linux removes the routes using the failed interface. r1 falls back from its removed `/24` to its existing `/22` through r2, but r4 has also lost the return route to h1, so end-to-end reachability still fails. Bringing the link up does not recreate these static entries. The command file records that failure, then restores r1's `50.0/24` and `80.0/24` entries and r4's `8.0/24` entry using `ip route replace`; it then verifies 3/3 h1-to-h3 replies and a final 12/12 host matrix. The later LPM demonstration deletes only the /24 while the physical link and return route remain working, so fallback through r2 succeeds.

Exit Mininet after restoring the link. Once the evidence and answers are complete:

```sh
python3 make_page3.py network.yaml
python3 verify_week3.py
```

Inspect `docs/week3/index.html`. This is generated output: edit the YAML, Python or evidence sources, then regenerate rather than hand-editing the page. The routing tables shown in HTML come from the model; `routes.txt` contains the independent running Linux tables. The generator imports `build_routed.py`, so run it where the Mininet Python package is available.

A small routing-table regression check, also run inside the container:

```sh
python3 - <<'PY'
import ipaddress
import re
from build_routed import load
from make_page3 import routing_tables_section
rendered = routing_tables_section(load("network.yaml"))
assert rendered.count("<h3>") == 4
assert rendered.count("<tr><td>") == 23
assert rendered.count("directly connected") == 12
for table in rendered.split("<h3>")[1:]:
    lengths = [ipaddress.ip_network(p).prefixlen for p in re.findall(r"<code>(.*?)</code>", table)]
    assert lengths == sorted(lengths, reverse=True)
print("PASS: all connected/static routes appear in longest-prefix-first order")
PY
```

## Completion checks

Actual container run: 2026-10-24 (Asia/Shanghai). All 12 directed LAN-host pairs succeeded, with 24/24 replies in the two-probe evidence file. After fault recovery the explicit matrix again received 12/12. The two guided IPv6 destinations each received 3/3. Evidence was collected by scripted execution of the real Mininet/Linux network; it is not a simulation of ping or traceroute, and not a claim of a student's manual terminal session.

- [x] Four routers, four LANs and a redundant router path; addresses do not overlap.
- [x] Every directed LAN-host pair passes both the model checker and the explicit four-host live ping matrix.
- [x] The two bad descriptions fail before network construction, with useful loop/missing-route messages.
- [x] All evidence files contain real command output, including the fault and restored state.
- [x] The summary covers the intended two LANs; the `/24` LPM behaviour matches the traces.
- [x] All four answers match the final design and observed results; no pending text remains.
- [x] The generated page shows every router's connected/static entries, longest prefix first, and no missing evidence warnings.
- [x] Commit actual work stages without rewriting history to manufacture progress.
- [ ] Publish at `https://lczssg.github.io/lab2/week3/` and check both this page and the existing Week 2 homepage.
- [ ] Submit the Week 3 link to the SPeCTRUM online-text assignment before its displayed deadline; verify the saved submission state.

Preparing files or generating a local page does not itself publish the page or submit the assignment. Check off items only after their actual execution and verification.
