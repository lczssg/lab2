#!/usr/bin/env python3
"""Week 7 lab, Steps 5 and 6: read every device and its site (course starter)."""
import json
import os
import random
import sys
import time
from collections import Counter
from urllib.parse import urljoin, urlsplit

import requests

API = os.environ.get("LAB_API_URL", "http://api:8000").rstrip("/")
MAX_ATTEMPTS = 16
MAX_TRANSIENT_ATTEMPTS = 6


class Client:
    """A logged-in client for the lab API."""

    def __init__(self):
        self.token = None
        self.requests = 0  # Every HTTP attempt, including logins and retries.

    def login(self):
        """Get a fresh token using credentials from the environment."""
        try:
            user, password = os.environ["LAB_USERNAME"], os.environ["LAB_PASSWORD"]
        except KeyError:
            sys.exit("Set LAB_USERNAME and LAB_PASSWORD in the environment first.")
        self.requests += 1
        r = requests.post(f"{API}/api/v1/auth/token", json={"username": user, "password": password},
                          timeout=5, allow_redirects=False)
        r.raise_for_status()
        if r.status_code != 200:
            raise ValueError(f"unexpected login status {r.status_code}")
        self.token = r.json()["token"]
        print(f"logged in as {user}")

    def request(self, method, url, *, body=None, key=None):
        """Send a lab resource request and retry only operations with safe effects."""
        if urlsplit(url)[:2] != urlsplit(API)[:2]:
            raise ValueError("resource URL points outside LAB_API_URL")
        if method not in {"GET", "PUT", "DELETE"} and (method != "POST" or not key):
            raise ValueError(f"{method} requires a safe retry strategy")
        if self.token is None:
            self.login()
        transient_errors = 0
        for attempt in range(1, MAX_ATTEMPTS + 1):
            headers = {"Authorization": f"Bearer {self.token}"}
            if key:
                headers["Idempotency-Key"] = key
            self.requests += 1
            label = f"{method} {urlsplit(url).path}"
            try:
                r = requests.request(method, url, json=body, headers=headers,
                                     timeout=5, allow_redirects=False)
            except (requests.ConnectionError, requests.Timeout) as error:
                if attempt == MAX_ATTEMPTS or transient_errors + 1 == MAX_TRANSIENT_ATTEMPTS:
                    raise
                reason = f"no response ({type(error).__name__})"
            else:
                if r.status_code == 401 and attempt < MAX_ATTEMPTS:
                    print(f"{label}: 401 {r.json()['error']}; logging in again")
                    self.login()
                    continue
                if r.status_code == 429 and attempt < MAX_ATTEMPTS:
                    delay = int(r.headers.get("Retry-After", "1"))
                    print(f"{label}: 429; waiting Retry-After {delay}s")
                    time.sleep(delay)
                    continue
                if r.status_code == 503 and attempt < MAX_ATTEMPTS and transient_errors + 1 < MAX_TRANSIENT_ATTEMPTS:
                    reason = "503 Service Unavailable"
                else:
                    if method == "DELETE" and r.status_code == 404:
                        return r  # Already absent, e.g. the first reply was lost.
                    r.raise_for_status()
                    if not 200 <= r.status_code < 300:
                        raise ValueError(f"{label}: unexpected status {r.status_code}")
                    if r.headers.get("Idempotent-Replayed") == "true":
                        print(f"{label}: {r.status_code} Idempotent-Replayed: true")
                    return r
            delay = 2 ** transient_errors + random.uniform(0, 0.25)
            transient_errors += 1
            print(f"{label}: {reason}; retrying in {delay:.2f}s")
            time.sleep(delay)

    def get_page(self, url):
        """GET one page, handling expired tokens, rate limits and transient failures."""
        return self.request("GET", url)

    def get_all(self, url):
        """Follow `next` and return all items and the first page's count header."""
        items, total = [], None
        visited = set()
        while url:
            if url in visited:
                raise ValueError("pagination returned a repeated URL")
            r = self.get_page(url)
            if not visited:
                total = r.headers.get("X-Total-Count")
            visited.add(url)
            page = r.json()
            items.extend(page["items"])
            url = urljoin(url, page["next"]) if page["next"] else None
        return items, total


def main():
    c = Client()
    devices, total = c.get_all(f"{API}/api/v1/devices?limit=10")
    if total is None or len(devices) != int(total):
        sys.exit("The count doesn't match X-Total-Count: some devices are missing.")
    with open("devices.json", "w", encoding="utf-8") as f:
        json.dump(devices, f, indent=2)
    print(f"{len(devices)} devices read (the API says {total}), in {c.requests} requests; saved devices.json")
    for site, n in sorted(Counter(d["site"] for d in devices).items()):
        print(f"  {site}: {n}")


if __name__ == "__main__":
    main()
