"""Small regression check for the assignment's data, validation and generated page.

Run in the course container: python3 verify_lab.py
"""
from copy import deepcopy
import ipaddress
import json
from pathlib import Path

import yaml

from build_topo import check, check_mine, load
from make_page import EVIDENCE, esc, links_section, mermaid_diagram

spec = load("topology.yaml")
assert len(spec["switches"]) >= 3 and len(spec["hosts"]) >= 6
assert spec == load("topology.json")
assert check_mine(spec) + check(spec) == []
assert all("ip" in host and "ipv6" in host for host in spec["hosts"])
nodes = set(spec["switches"]) | {host["name"] for host in spec["hosts"]}
neighbours = {name: set() for name in nodes}
for a, b in spec["links"]:
    neighbours[a].add(b)
    neighbours[b].add(a)
visited, pending = set(), [next(iter(nodes))]
while pending:
    name = pending.pop()
    if name not in visited:
        visited.add(name)
        pending.extend(neighbours[name] - visited)
assert visited == nodes
assert len(spec["links"]) == len(nodes) - 1  # Connected tree, with no bridge loop.

bad4 = deepcopy(spec)
bad4["hosts"][1]["ip"] = spec["hosts"][0]["ip"].split("/")[0] + "/16"
assert len(check(bad4)) == 1 and "10.1.0.1" in check(bad4)[0]
bad6 = deepcopy(spec)
address = ipaddress.ip_interface(spec["hosts"][0]["ipv6"]).ip
bad6["hosts"][1]["ipv6"] = address.exploded.upper() + "/48"
assert len(check(bad6)) == 1 and "fd00:6101::1" in check(bad6)[0]
badlink = deepcopy(spec)
badlink["links"].append(["h6", "s9"])
assert len(check(badlink)) == 1 and "unknown node s9" in check(badlink)[0]
assert len(check(load("bad.yaml"))) == 3
outside = deepcopy(spec)
outside["hosts"][0]["ip"] = "10.2.0.1/24"
assert check_mine(outside)
assert "&lt;" in links_section({"links": [["h<1", "s&1"]]})
assert "&amp;" in links_section({"links": [["h<1", "s&1"]]})
assert links_section(spec).count("<li>") == len(spec["links"])
diagram = mermaid_diagram(spec)
assert diagram.startswith("graph LR\n")
assert diagram.count(" --- ") == len(spec["links"])
assert all(host["ip"].split("/")[0] in diagram for host in spec["hosts"])
for _, path, _ in EVIDENCE:
    assert Path(path).read_text().strip(), path
assert "0% dropped (30/30 received)" in Path("evidence/pingall.txt").read_text()
assert "dadfailed" in Path("evidence/dad.txt").read_text()
assert len(Path("evidence/ipv6-all-pairs.txt").read_text().splitlines()) == 30
page = yaml.safe_load(Path("page.yaml").read_text())
assert set(page["answers"]) == {"planes", "learning", "kind", "two_am", "model", "check", "git"}
assert all(str(item["answer"]).strip() for item in page["answers"].values())
html = Path("docs/index.html").read_text()
assert esc(diagram) in html
assert links_section(spec) in html
assert all(text not in html for text in ("TODO", "Missing:", "(Not answered yet.)", "YOUR-"))
assert page["repository"] == "https://github.com/lczssg/lab2"
print("PASS: personal dual-stack tree, YAML/JSON equality, normalised duplicate checks,")
print("bad-link rejection, escaped link HTML, generated diagram, evidence and seven answers.")

