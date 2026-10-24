"""Check collected evidence and the generated page; does not simulate packet delivery."""
import ipaddress
import json
from pathlib import Path
import re

from build_routed import check_paths, check_spec, load, plan
from make_page3 import EVIDENCE, routing_tables_section


spec = load("network.yaml")
assert check_spec(spec) == check_paths(spec) == []
for _, filename, _ in EVIDENCE:
    assert Path(filename).read_text().strip(), filename
pings = Path("evidence3/pingall.txt").read_text()
assert len(re.findall(r"^== h\d -> h\d$", pings, re.M)) == 12
assert len(re.findall(r"2 packets transmitted, 2 received, 0% packet loss", pings)) == 12
session = Path("evidence3/session.txt").read_text()
assert session.count("0% dropped (12/12 received)") == 2
for error in ("Traceback", "Unknown command", "Read-only file system", "RTNETLINK answers"):
    assert error not in session, error
checks = Path("evidence3/check.txt").read_text()
assert "loop r3 -> r4 -> r3" in checks and "h2 to h3: r2 has no route" in checks
assert checks.count("nothing was built") == 2
traces = Path("evidence3/traces.txt").read_text()
assert all(destination in traces for destination in ("10.1.48.10", "10.1.50.10", "10.1.80.10"))
assert " *" not in traces
assert Path("evidence3/summary.txt").read_text().count("via 10.1.34.1") == 2
failure = Path("evidence3/failure.txt").read_text()
down = failure.split("== r1-r4 down:")[1].split("== link up alone:")[0]
assert "via 10.1.12.2" in down and " *" in down
link_only = failure.split("== link up alone:")[1].split("== static routes reinstalled:")[0]
assert "100% packet loss" in link_only
recovered = failure.split("== static routes reinstalled:")[1]
assert "3 packets transmitted, 3 received, 0% packet loss" in recovered
fallback = Path("evidence3/lpm-fallback.txt").read_text()
assert "via 10.1.14.2" in fallback and "via 10.1.12.2" in fallback and " *" not in fallback
ipv6 = Path("week3/ping-ipv6.txt").read_text()
assert ipv6.count("3 packets transmitted, 3 received, 0% packet loss") == 2
assert "Time to live exceeded" in Path("week3/guided-session.txt").read_text()
assert "nothing was configured" in Path("week3/check-loop.txt").read_text()
assert "nothing was configured" in Path("week3/check-missing.txt").read_text()

tables = routing_tables_section(spec)
assert tables.count("<h3>") == 4 and tables.count("<tr><td>") == 23
assert tables.count("directly connected") == sum(len(plan(spec)[r]) for r in spec["routers"]) == 12
for table in tables.split("<h3>")[1:]:
    lengths = [ipaddress.ip_network(p).prefixlen for p in re.findall(r"<code>(.*?)</code>", table)]
    assert lengths == sorted(lengths, reverse=True)
page = Path("docs/week3/index.html").read_text()
embedded = re.search(r'<script type="application/json" id="network-data">(.*?)</script>', page, re.S)
assert embedded and json.loads(embedded[1]) == spec
assert tables in page
for placeholder in ("TODO", "Missing:", "Pending the real", "Not answered yet", "YOUR-USERNAME"):
    assert placeholder not in page, placeholder
for _, filename, _ in EVIDENCE:
    assert filename in page
assert page.count('<section id="answer-') == 4
assert 'href="https://github.com/lczssg/lab2"' in page
print("PASS: 12 live host pairs (24/24 echo replies), final 12/12 recovery, bad configs rejected;")
print("IPv6 guided pings, summaries, LPM fallback, failure/recovery and generated page agree.")
