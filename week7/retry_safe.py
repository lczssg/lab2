#!/usr/bin/env python3
"""Step 4: retry one logical ACL append with the key created before the first send."""
import os
import re
import sys
from uuid import uuid4

from inventory import API, Client


def main():
    if len(sys.argv) != 2 or not re.fullmatch(r"[0-9]{4}", sys.argv[1]):
        sys.exit("usage: python3 retry_safe.py <last 4 digits of your student ID>")
    nn = int(sys.argv[1][2:])
    entry = {
        "action": "deny",
        "src": f"10.{nn}.30.0/24",
        "dst": f"10.{nn}.20.0/24",
        "protocol": "tcp",
        "port": 22,
        "description": "guests may not SSH to servers",
    }
    client = Client()
    client.token = os.environ["LAB_API_TOKEN"]
    response = client.request("POST", f"{API}/api/v1/acl/entries", body=entry, key=uuid4().hex)
    print(f"{response.status_code} {response.reason}: {response.json()}")


if __name__ == "__main__":
    main()
