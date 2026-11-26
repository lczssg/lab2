#!/usr/bin/env python3
"""Reconcile the Week 7 lab VLANs and ordered ACL entries with one intent file."""
import argparse
import ipaddress
import json
import re
import sys
from pathlib import Path
from uuid import uuid4

import requests
import yaml

from inventory import API, Client

VLANS = "/api/v1/vlans"
ACL = "/api/v1/acl/entries"
ACL_DEFAULTS = {"protocol": "any", "port": None, "description": ""}


def acl_fields(entry):
    """Compare the user-controlled fields, with the same defaults as the API."""
    return {"action": entry["action"], "src": entry["src"], "dst": entry["dst"],
            **{k: entry.get(k, default) for k, default in ACL_DEFAULTS.items()}}


def load_intent(path):
    """Load and validate the entire file before allowing any API writes."""
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or not re.fullmatch(r"[0-9]{4}", str(data.get("student_id_last4"))):
        raise ValueError("student_id_last4 must be four digits")
    nn = int(str(data["student_id_last4"])[-2:])
    block = ipaddress.IPv4Network(f"10.{nn}.0.0/16")
    if not isinstance(data.get("vlans"), list) or not isinstance(data.get("acl"), list):
        raise ValueError("vlans and acl must both be lists")

    vlans = {}
    for entry in data["vlans"]:
        if not isinstance(entry, dict) or set(entry) != {"id", "name"}:
            raise ValueError("every VLAN needs an id and a name")
        vid, name = entry["id"], entry["name"]
        if type(vid) is not int or not 2 <= vid <= 4094 or vid in vlans:
            raise ValueError("VLAN IDs must be unique integers from 2 to 4094")
        if not isinstance(name, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,32}", name):
            raise ValueError(f"invalid VLAN name for VLAN {vid}")
        vlans[vid] = name

    acl = []
    required = {"action", "src", "dst"}
    for entry in data["acl"]:
        if not isinstance(entry, dict) or not required <= entry.keys() <= required | ACL_DEFAULTS.keys():
            raise ValueError("ACL rows need action, src and dst, with optional protocol, port and description")
        rule = acl_fields(entry)
        if rule["action"] not in ("permit", "deny") or rule["protocol"] not in ("any", "tcp", "udp", "icmp"):
            raise ValueError("invalid ACL action or protocol")
        for field in ("src", "dst"):
            cidr = rule[field]
            if not isinstance(cidr, str) or "/" not in cidr:
                raise ValueError(f"ACL {field} must be a network in CIDR notation")
            network = ipaddress.IPv4Network(cidr)
            if not network.subnet_of(block):
                raise ValueError(f"ACL {field} must be within {block}")
            rule[field] = str(network)
        port = rule["port"]
        if port is not None and (rule["protocol"] not in ("tcp", "udp") or type(port) is not int or not 1 <= port <= 65535):
            raise ValueError("ACL ports must be integers from 1 to 65535 and require tcp or udp")
        if not isinstance(rule["description"], str) or rule in acl:
            raise ValueError("ACL rows must be unique and descriptions must be strings")
        acl.append(rule)
    return vlans, acl


def read_state(client):
    vlans, _ = client.get_all(API + VLANS)
    acl, _ = client.get_all(API + ACL)
    return {v["id"]: v["name"] for v in vlans if v["id"] != 1}, acl


def make_plan(current, desired):
    current_vlans, current_acl = current
    desired_vlans, desired_acl = desired
    plan = []
    for vid, name in sorted(desired_vlans.items()):
        if current_vlans.get(vid) != name:
            action = "rename VLAN" if vid in current_vlans else "create VLAN"
            plan.append((action, "PUT", f"{VLANS}/{vid}", {"name": name}))
    for vid in sorted(current_vlans.keys() - desired_vlans.keys()):
        plan.append(("delete VLAN", "DELETE", f"{VLANS}/{vid}", None))

    # POST can only append. Retain the longest prefix already in relative order.
    kept = 0
    for row in current_acl:
        if kept < len(desired_acl) and acl_fields(row) == desired_acl[kept]:
            kept += 1
        else:
            plan.append(("delete ACL entry", "DELETE", f"{ACL}/{row['id']}", None))
    for rule in desired_acl[kept:]:
        plan.append(("append ACL entry", "POST", ACL, rule))
    return plan


def show_plan(plan):
    if not plan:
        print("Plan: empty (0 writes)", flush=True)
        return
    print(f"Plan: {len(plan)} writes")
    for action, method, path, body in plan:
        suffix = f" {json.dumps(body, ensure_ascii=False)}" if body is not None else ""
        print(f"  {action}: {method} {path}{suffix}", flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("intent", type=Path)
    parser.add_argument("--dry-run", action="store_true", help="print the plan without resource writes")
    args = parser.parse_args()
    client = Client()
    try:
        desired = load_intent(args.intent)
        plan = make_plan(read_state(client), desired)
        show_plan(plan)
        if args.dry_run:
            print("Dry run: no resource writes sent.")
            return 0

        for _, method, path, body in plan:
            key = uuid4().hex if method == "POST" else None
            client.request(method, API + path, body=body, key=key)

        remaining = make_plan(read_state(client), desired)
        if remaining:
            print("Verification failed. The API still differs from intent.", file=sys.stderr)
            show_plan(remaining)
            return 1
        vlans, acl = desired
        print(f"Verified: state matches intent ({len(vlans)} managed VLANs, {len(acl)} ACL entries).")
        return 0
    except (OSError, KeyError, ValueError, yaml.YAMLError, requests.RequestException) as error:
        print(f"Sync failed: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
