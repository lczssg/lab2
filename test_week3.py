"""Model checks, not Mininet evidence. Run in the course container: python3 test_week3.py."""
from copy import deepcopy
import ipaddress

import build_routed as assignment
import routers as guided


spec = assignment.load("network.yaml")
assert assignment.check_spec(spec) == []
assert assignment.check_paths(spec) == []
assert len(spec["routers"]) == len(spec["lans"]) == 4
assert len(spec["links"]) == 4  # Connected ring has one redundant edge.

expected = {
    ("h1", "h2"): ["r1", "r2"],
    ("h1", "h3"): ["r1", "r4", "r3"],
    ("h1", "h4"): ["r1", "r4"],
    ("h2", "h1"): ["r2", "r1"],
    ("h2", "h3"): ["r2", "r3"],
    ("h2", "h4"): ["r2", "r3", "r4"],
    ("h3", "h1"): ["r3", "r4", "r1"],
    ("h3", "h2"): ["r3", "r2"],
    ("h3", "h4"): ["r3", "r4"],
    ("h4", "h1"): ["r4", "r1"],
    ("h4", "h2"): ["r4", "r3", "r2"],
    ("h4", "h3"): ["r4", "r3"],
}
endpoints = assignment.hosts(spec)
assert len(expected) == len(endpoints) * (len(endpoints) - 1) == 12
for (src, dst), path in expected.items():
    destination = endpoints[dst][0]
    assert path[0] == endpoints[src][1]
    for index, router in enumerate(path):
        action, next_hop = assignment.lookup(spec, router, destination)
        if index == len(path) - 1:
            assert action == "connected", (src, dst, router)
        else:
            assert action == "via", (src, dst, router)
            assert assignment.owner(spec, next_hop) == path[index + 1], (src, dst, router)

summary = ipaddress.ip_network("10.1.48.0/22")
assert [h for h, (address, _) in endpoints.items() if address in summary] == ["h2", "h3"]
for host in ("h2", "h3"):
    assert assignment.lookup(spec, "r4", endpoints[host][0]) == ("via", ipaddress.ip_address("10.1.34.1"))
fallback = deepcopy(spec)
fallback["routes"]["r1"] = [r for r in fallback["routes"]["r1"] if r["to"] != "10.1.50.0/24"]
assert assignment.check_paths(fallback) == []
assert assignment.lookup(fallback, "r1", endpoints["h3"][0]) == ("via", ipaddress.ip_address("10.1.12.2"))

for filename, expected_problem in (("loop.yaml", "loop r3 -> r4 -> r3"), ("missing.yaml", "h2 to h3: r2 has no route")):
    bad = assignment.load(filename)
    assert assignment.check_spec(bad) == []  # Structurally valid: needs the path checker.
    problems = assignment.check_paths(bad)
    assert any(expected_problem in p for p in problems), (filename, problems)
invalid = deepcopy(spec)
invalid["routes"]["r1"][0]["via"] = "10.1.12.3"
assert any("not a router" in p for p in assignment.check_paths(invalid))
invalid["routes"]["r1"][0]["via"] = "10.1.8.10"  # Host addresses are not forwarding routers.
assert any("not a router" in p for p in assignment.check_paths(invalid))

routes = guided.load_routes("routes.yaml")
assert guided.check_routes(routes, 1) == guided.check_paths(routes, 1) == []
loop = deepcopy(routes)
loop["r3"][0]["via"] = "10.1.13.1"  # h3 loops r1 -> r3 -> r1.
assert any("loop r1 -> r3 -> r1" in p for p in guided.check_paths(loop, 1))
missing = deepcopy(routes)
missing["r2"] = []
assert any("h2 to h1: r2 has no route" in p for p in guided.check_paths(missing, 1))

print("PASS: all 12 directed model paths, /22 coverage, /24 preference and fallback;")
print("assignment and guided checkers reject loops and missing routes; invalid next hops rejected.")
