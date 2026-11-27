#!/usr/bin/env python3
"""Check an intent file against wic2005-intent.yang, with yanglint, before anything touches the network.

    python3 validate.py intent.yaml                     # exit 0 if valid, 1 if not
    python3 validate.py intent.yaml --emit-json x.json  # also write the JSON that was checked

The RULES live in your YANG module, not here. This script only translates intent.yaml into the
JSON encoding of your model (RFC 7951) and asks yanglint. Keep it that way: a rule checked in
Python instead of YANG doesn't count.

Week 8 assignment starter: finish to_json(). Run it in the yanglab container (pip install pyyaml).
"""
import argparse
import json
import pathlib
import subprocess
import sys
import tempfile

import yaml

HERE = pathlib.Path(__file__).resolve().parent
MODULE = HERE / "wic2005-intent.yang"


def to_json(intent):
    """intent.yaml's structure -> RFC 7951 JSON for your module.

    Copy the values across as they are, even wrong ones: a VLAN 4095 in the YAML must reach
    yanglint as 4095, so that your model is what rejects it.
    """
    return {"wic2005-intent:intent": intent}


_UNLOADED = object()


def validate(path, emit=None, *, intent=_UNLOADED):
    """Return (ok, message) and optionally write the exact JSON checked."""
    try:
        if intent is _UNLOADED:
            intent = yaml.safe_load(pathlib.Path(path).read_text(encoding="utf-8"))
        data = json.dumps(to_json(intent), indent=2, allow_nan=False)
        if emit:
            pathlib.Path(emit).write_text(data + "\n", encoding="utf-8")
        with tempfile.TemporaryDirectory() as tmp:
            json_file = pathlib.Path(tmp) / "intent.json"
            json_file.write_text(data, encoding="utf-8")
            p = subprocess.run(
                ["yanglint", "-t", "config", str(MODULE), str(json_file)],
                capture_output=True,
                text=True,
            )
    except (OSError, ValueError, TypeError, yaml.YAMLError) as e:
        return False, str(e)
    lines = (p.stdout + p.stderr).splitlines()
    diagnostics = [line for line in lines if not line.startswith("YANGLINT[E]")]
    return p.returncode == 0, "\n".join(diagnostics or lines).strip()


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("intent")
    ap.add_argument("--emit-json", metavar="FILE")
    a = ap.parse_args()
    ok, msg = validate(a.intent, a.emit_json)
    if ok:
        print(f"VALID: {a.intent} matches {MODULE.name}")
        return 0
    print(f"INVALID: {a.intent}")
    print(msg)
    return 1


if __name__ == "__main__":
    sys.exit(main())
