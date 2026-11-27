#!/usr/bin/env python3
"""Reconcile the lab VLANs and ordered ACL entries with one intent file."""
import argparse
import json
import sys
from pathlib import Path
from uuid import uuid4

import requests
import yaml

from inventory import API, Client
from validate import validate

VLANS = "/api/v1/vlans"
ACL = "/api/v1/acl/entries"
ACL_DEFAULTS = {"protocol": "any", "port": None, "description": ""}


def acl_fields(entry):
    """Compare the user-controlled fields, with the same defaults as the API."""
    return {"action": entry["action"], "src": entry["src"], "dst": entry["dst"],
            **{k: entry.get(k, default) for k, default in ACL_DEFAULTS.items()}}


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
    try:
        intent = yaml.safe_load(args.intent.read_text(encoding="utf-8"))
        ok, message = validate(args.intent, intent=intent)
        if not ok:
            print(f"INVALID: {args.intent}\n{message}", file=sys.stderr)
            return 1
        desired = (
            {entry["id"]: entry["name"] for entry in intent["vlans"]},
            [acl_fields(entry) for entry in intent["acl"]],
        )
        client = Client()
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
