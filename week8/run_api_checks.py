#!/usr/bin/env python3
"""Run the positive sync and API comparisons against a fresh, dedicated lab API."""
import json
import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

from requests import HTTPError
import yaml

from inventory import API, Client
from sync import ACL, VLANS, acl_fields
from validate import MODULE


def run(*command):
    print("$ " + " ".join(map(str, command)), flush=True)
    return subprocess.check_output(command, text=True)


def run_sync(*args):
    output = run(sys.executable, "sync.py", "intent.yaml", *args)
    print(output, end="")
    return output


def reject(client, method, path, body, diagnostic, *, key=None):
    print(f"$ {method} {path} {json.dumps(body)}")
    try:
        client.request(method, API + path, body=body, key=key)
    except HTTPError as error:
        response = error.response
        print(f"HTTP {response.status_code} {json.dumps(response.json())}")
        assert response.status_code == 422 and diagnostic in response.json()["error"]
    else:
        raise AssertionError("The course API accepted the invalid request")


def main():
    client = Client()
    source = yaml.safe_load(Path("intent.yaml").read_text(encoding="utf-8"))
    audit_url = API + "/api/v1/lab/audit"
    initial_vlans, _ = client.get_all(API + VLANS)
    initial_acl, _ = client.get_all(API + ACL)
    assert {row["id"] for row in initial_vlans} == {1, 10, 20, 99} and not initial_acl
    assert client.request("GET", audit_url).json()["writes"] == 0
    print("Fresh API: 3 managed VLANs, reserved VLAN 1, no ACL entries, no audited writes.")

    assert "Plan: 11 writes" in run_sync("--dry-run")
    assert client.request("GET", audit_url).json()["writes"] == 0
    print("Audit after valid dry run: 0 writes.")
    assert "Verified: state matches intent (6 managed VLANs, 4 ACL entries)." in run_sync()
    assert client.request("GET", audit_url).json()["writes"] == 11
    assert "Plan: empty (0 writes)" in run_sync()

    vlans, _ = client.get_all(API + VLANS)
    entries, _ = client.get_all(API + ACL)
    assert {v["id"]: v["name"] for v in vlans} == {
        1: "default", **{v["id"]: v["name"] for v in source["vlans"]}
    }
    assert [acl_fields(entry) for entry in entries] == [acl_fields(entry) for entry in source["acl"]]
    print("Confirmed exact VLANs including default VLAN 1 and the four ACL rules in order.")

    source["acl"][0]["src"] = "10.1.40.5/24"
    with TemporaryDirectory() as directory:
        fixture = Path(directory) / "host-bits.yaml"
        encoded = Path(directory) / "host-bits.json"
        fixture.write_text(yaml.safe_dump(source, sort_keys=False), encoding="utf-8")
        print(run(sys.executable, "validate.py", fixture, "--emit-json", encoded), end="")
        original = json.loads(encoded.read_text(encoding="utf-8"))["wic2005-intent:intent"]["acl"][0]["src"]
        output = run("yanglint", "-t", "config", "-f", "json", str(MODULE), encoded)
        canonical = json.loads(output)["wic2005-intent:intent"]["acl"][0]["src"]
        print(f"Emitted prefix: {original}. Prefix from yanglint's JSON printer: {canonical}.")
    reject(client, "POST", ACL, acl_fields(source["acl"][0]), "src must be a network in CIDR form",
           key="week8-host-bits-check")
    reject(client, "PUT", VLANS + "/4095", {"name": "out-of-range"}, "4094")
    assert client.request("GET", audit_url).json()["writes"] == 11
    print("Final audit: 11 writes total. Second apply and rejected API probes added 0.")


if __name__ == "__main__":
    main()
