# WIC2005 Lab 2 — A dual-stack network built from data

**Student ID suffix:** 6101 · **Lab date:** 17 October 2026

[Published assignment](https://lczssg.github.io/lab2/) · [Repository](https://github.com/lczssg/lab2) · [Official Week 2 instructions](https://firdaussahran.github.io/wic2005/weeks/week-02/)

## Design and purpose

The final network is a branching tree with **4 Linux bridges, 6 hosts and 9 links**.
h1 attaches to s1; h2 and h3 to s2; h4 and h5 to s3; h6 to s4.
The inter-switch links are s1–s2, s1–s3 and s3–s4.

I chose an asymmetric tree so the MAC table can distinguish a local host from groups
of hosts reached through an uplink. It is connected and has no forwarding loop.
There is no redundant path: a failed inter-switch link would disconnect its branch.
All hosts share IPv4 10.1.0.0/24 and IPv6 fd00:6101::/64, within the personal blocks
10.1.0.0/16 and fd00:6101::/32 derived from the suffix 6101.
These are bridged subnets; this lab does not implement inter-subnet routing.

One data model produces two outputs:
- build_topo.py reads topology.yaml or topology.json, validates it and builds Mininet.
- make_page.py uses the same loading and validation functions to generate docs/index.html.

The seven analysis answers are in page.yaml and on the published page.
SOURCE.md records the official starter-file blob hashes.

## Environment

Windows / PowerShell with Git 2.45.1, Docker Desktop 4.83.0 and Linux Docker Engine 29.6.2.
The official firdaussahran/netlab-mininet:1.0 image supplies Mininet, Python and PyYAML.
The image used was:

    firdaussahran/netlab-mininet@sha256:61e473c216738b60a74196ac741b915a40bca86fa0aa2e16e7d753569d1b83b6

Run the Python scripts **inside that Linux container**: make_page.py also imports
build_topo.py, which imports Mininet. No extra Python packages need to be installed.

## Reproduce from a clean checkout

Start Docker Desktop. In Windows PowerShell:

~~~powershell
git clone https://github.com/lczssg/lab2.git
cd lab2
docker run -it --rm --network none --cap-add NET_ADMIN --cap-add SYS_ADMIN --mount "type=bind,source=$($PWD.Path),target=/lab" -w /lab firdaussahran/netlab-mininet:1.0
~~~

This mounts only the checkout, publishes no ports and gives the container no external
network. It does not need --privileged. Mininet's hosts communicate over internal
virtual links. The diagram is rendered later by the visitor's browser, which needs
internet access to load Mermaid.

Inside the container:

~~~sh
python3 build_topo.py topology.yaml
~~~

At mininet>:

~~~text
net
pingall
h1 ping -6 -c 1 fd00:6101::6
exit
~~~

A short delay may be needed after network creation for IPv6 Duplicate Address
Detection. The saved command files begin with a three-second wait.

## Recollect the assignment evidence

The next steps deliberately overwrite the evidence with a fresh run. The fault
injection affects only the temporary Mininet hosts, and exit destroys that topology.

Inside the container, the malformed fixture should be rejected with a nonzero exit
status and three PROBLEM lines:

~~~sh
python3 -u build_topo.py bad.yaml > evidence/check.txt 2>&1
cat evidence/check.txt
~~~

Now run the full saved command sequence:

~~~sh
python3 -u build_topo.py topology.yaml < commands/06-assignment.txt 2>&1 | tee evidence/final-session.txt
~~~

It tests normal connectivity first, saves the neighbour and MAC tables, and only then
adds copies of h1's addresses to h2 to demonstrate IPv6 DAD and IPv4 address acceptance.
The commands and raw output are kept separately because piped Mininet prompts can
appear together when stdout and stderr are interleaved.

Extract the pingall block and IPv6 matrix directly from that raw session:

~~~sh
python3 - <<'PY'
from pathlib import Path
import re
session = Path("evidence/final-session.txt").read_text()
ping = re.search(r"(?ms)^\*\*\* Ping: testing ping reachability.*?^\*\*\* Results: [^\r\n]*", session)
assert ping and "0% dropped (30/30 received)" in ping.group()
Path("evidence/pingall.txt").write_text(ping.group() + "\n")
ipv6 = re.findall(r"\bh[1-6] -> h[1-6]: 1 packets transmitted, 1 received, 0% packet loss[^\r\n]*", session)
assert len(ipv6) == len(set(ipv6)) == 30
Path("evidence/ipv6-all-pairs.txt").write_text("\n".join(ipv6) + "\n")
PY
~~~

Rebuild from JSON to check the same network and remove the injected duplicates:

~~~sh
python3 -u build_topo.py topology.json < commands/07-recovery.txt 2>&1 | tee evidence/final-json-recovery.txt
python3 make_page.py topology.yaml
python3 verify_lab.py
~~~

Changing topology.yaml means also regenerating topology.json before this comparison:

~~~sh
python3 -c 'import json,yaml; from pathlib import Path; Path("topology.json").write_text(json.dumps(yaml.safe_load(Path("topology.yaml").read_text()),indent=2)+"\n")'
~~~

make_page.py also rejects bad.yaml before writing anything. The saved
evidence/page-rejection.txt records the three errors; the generated HTML's SHA-256
was checked to be unchanged by that rejected attempt.

## Observed results

| Requirement | Actual evidence |
| --- | --- |
| Initial 3-host network | evidence/01-initial.txt: IPv4 6/6 and IPv6 replies |
| Expanded 4-host network | evidence/02-expanded.txt: IPv4 12/12 |
| Same network from JSON | evidence/03-json.txt: IPv4 12/12 |
| Duplicate addresses before checks | evidence/04-duplicate-before-check.txt: IPv4 11/12; h4 IPv6 dadfailed |
| Duplicate addresses rejected | evidence/05-duplicate-rejected.txt; restored 12/12 in evidence/05-restored.txt |
| Final 6-host IPv4 network | evidence/pingall.txt: 0% dropped, 30/30 |
| Final 6-host IPv6 network | evidence/ipv6-all-pairs.txt: all 30 directed pairs received replies |
| ARP and IPv6 neighbour learning | evidence/neigh.txt: both address families map to host MAC addresses |
| Bridge learning | evidence/macs.txt: s1 port 1 -> h1, port 2 -> h2/h3, port 3 -> h4/h5/h6 |
| Runtime duplicate demonstration | evidence/dad.txt: fd00:6101::1 dadfailed; 10.1.0.1 accepted as secondary |
| Both duplicate families and unknown endpoint | evidence/check.txt: three PROBLEM lines for bad.yaml |
| Clean rebuild after fault | evidence/final-json-recovery.txt: 30/30; h2 has only its intended global addresses |
| Automated regression check | evidence/verification.txt |

The 11/12 duplicate-IP result describes this actual run, not a guarantee for every run:
ARP cache contents and reply timing can change the symptoms.
pingall checks IPv4 only. A successful ping proves a reply was received, not that an
address was unique or the intended host answered.

Local interface entries marked 'yes' in a bridge MAC table are not learned host
entries. Background IPv6 messages can also cause learning.
Mininet printed resource-limit and bridge-netfilter warnings in this environment;
the recorded functional tests passed. No host sysctl was changed to hide warnings.

## Git history and the earlier experiments

At least five commits were required; the history preserves the actual stages.
Use git log --oneline and git show <commit> to inspect the changes.
The four-host fault experiment was committed before duplicate validation existed.
To reproduce that stage, use a separate checkout or worktree at commit 753ea7e,
run build_topo.py with examples/lab-duplicate.yaml and commands/04-duplicate.txt.
The current script intentionally rejects that fixture.

The final topology.json describes the final six-host network. Earlier JSON and
topology versions remain available in their commits.

## Publishing and submission

GitHub Pages publishes branch main, folder /docs.
After changing topology.yaml or page.yaml, regenerate docs/index.html and commit it.
Check the online diagram, evidence, answers and repository link after pushing.

The submission link is https://lczssg.github.io/lab2/ .
The official deadline is before the Week 3 class on Friday 23 October 2026;
the exact LMS cutoff should be checked in Spectrum. Spectrum submission is done
by the student.

Only the last four student-ID digits are used. No full student ID, personal name,
password or token is included in the assignment files.
AI assisted implementation and documentation with lecturer permission; the evidence
comes from actual local Mininet runs.

