#!/bin/sh
# Reproduce the guided lab from this folder inside yanglab.
set -eu
cd "$(dirname "$0")"
M=/usr/local/share/yang/modules
tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT
mkdir "$tmp/wifi"

expect() {
    want=$1
    shift
    printf '\n$ %s\n' "$*"
    status=0
    "$@" 2>&1 || status=$?
    printf 'exit=%s (expected %s)\n' "$status" "$want"
    [ "$status" -eq "$want" ]
}

printf '%s\n' '=== Step 0: Tools I ran ==='
expect 0 python3 --version
expect 0 pyang --version
expect 0 yanglint --version
printf '\nIETF module directory: %s\n' "$M/ietf"
ls "$M/ietf"

printf '\n%s\n' '=== Step 1: Interface model and base identity ==='
expect 0 pyang -f tree "$M/ietf/ietf-interfaces.yang"
expect 0 grep -n -A 3 'identity ethernetCsmacd' "$M/iana/iana-if-type.yang"

printf '\n%s\n' '=== Step 2: IP augmentation ==='
pyang -f tree "$M/ietf/ietf-ip.yang" > "$tmp/ip-tree.txt"
printf '$ pyang -f tree %s/ietf/ietf-ip.yang | head\n' "$M"
head "$tmp/ip-tree.txt"
expect 0 pyang -f tree --tree-path /interfaces/interface/ipv4/address \
    "$M/ietf/ietf-interfaces.yang" "$M/ietf/ietf-ip.yang"

printf '\n%s\n' '=== Step 3: Interface data ==='
printf '$ python3 (generate four copies of interfaces.json; change one field per copy)\n'
python3 - "$tmp" <<'PY'
import json
import sys
from pathlib import Path

for case in ("prefix-33", "type-ethernet", "ip-300", "missing-name"):
    data = json.loads(Path("interfaces.json").read_text())
    eth1, lo0 = data["ietf-interfaces:interfaces"]["interface"]
    address = eth1["ietf-ip:ipv4"]["address"][0]
    if case == "prefix-33":
        address["prefix-length"] = 33
    elif case == "type-ethernet":
        eth1["type"] = "iana-if-type:ethernet"
    elif case == "ip-300":
        address["ip"] = "10.1.1.300"
    else:
        del lo0["name"]
    (Path(sys.argv[1]) / f"{case}.json").write_text(json.dumps(data, indent=2) + "\n")
PY
set -- "$M/ietf/ietf-interfaces.yang" "$M/ietf/ietf-ip.yang" "$M/iana/iana-if-type.yang"
expect 0 yanglint -t config -p "$M" "$@" interfaces.json
for case in prefix-33 type-ethernet ip-300 missing-name; do
    expect 1 yanglint -t config -p "$M" "$@" "$tmp/$case.json"
done

printf '\n%s\n' '=== Step 4: VLAN example ==='
expect 0 pyang --strict example-vlans.yang
expect 0 pyang -f tree example-vlans.yang
expect 0 yanglint -t config example-vlans.yang vlans-good.json
for f in vlans-bad-*.json; do
    expect 1 yanglint -t config example-vlans.yang "$f"
done

printf '\n%s\n' '=== Step 5: Wi-Fi initial model and data ==='
cp old/example-wifi.yang "$tmp/wifi/"
expect 0 pyang --strict -p . "$tmp/wifi/example-wifi.yang"
expect 0 pyang -f tree -p . "$tmp/wifi/example-wifi.yang"
expect 0 yanglint -p . -t config "$tmp/wifi/example-wifi.yang" wifi-good.json
for f in wifi-bad-*.json; do
    expect 1 yanglint -p . -t config "$tmp/wifi/example-wifi.yang" "$f"
done

printf '\n%s\n' '=== Step 6: Configuration and operational data ==='
expect 1 yanglint -t config example-vlans.yang vlans-state.json
expect 0 yanglint example-vlans.yang vlans-state.json
expect 1 yanglint -p "$M" "$@" interfaces.json
expect 1 yanglint -t config example-wifi.yang wifi-clients.json
expect 0 yanglint example-wifi.yang wifi-clients.json

printf '\n%s\n' '=== Step 7: Wi-Fi revision check ==='
expect 0 pyang --strict example-wifi.yang
expect 0 pyang -P . --check-update-from old/example-wifi.yang example-wifi.yang
for change in mandatory-passphrase remove-hidden narrow-passphrase; do
    printf '\nMutation: %s\n' "$change"
    case "$change" in
        mandatory-passphrase)
            sed '/leaf passphrase {/a\        mandatory true;' \
                example-wifi.yang > "$tmp/wifi/example-wifi.yang"
            ;;
        remove-hidden)
            sed '/^      leaf hidden {/,/^      }/d' example-wifi.yang > "$tmp/wifi/example-wifi.yang"
            ;;
        narrow-passphrase)
            sed 's/length "8\.\.63"/length "12..63"/' example-wifi.yang > "$tmp/wifi/example-wifi.yang"
            ;;
    esac
    expected_status=1
    [ "$change" != narrow-passphrase ] || expected_status=0
    expect "$expected_status" pyang -p . -P . --check-update-from old/example-wifi.yang "$tmp/wifi/example-wifi.yang"
done

printf '\n%s\n' 'Test old data against both lengths (passphrase is abcdefgh)'
sed s/correct-horse-battery/abcdefgh/ wifi-good.json > "$tmp/wifi-short-passphrase.json"
expect 0 yanglint -p . -t config old/example-wifi.yang "$tmp/wifi-short-passphrase.json"
expect 1 yanglint -p . -t config "$tmp/wifi/example-wifi.yang" "$tmp/wifi-short-passphrase.json"
