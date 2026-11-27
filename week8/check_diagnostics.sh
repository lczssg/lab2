#!/bin/sh
# Check that independently validating each emitted JSON gives the intended error first.
set -eu
cd "$(dirname "$0")"
tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT

for fixture in tests/bad-*.yaml; do
    name=$(basename "$fixture")
    expected=$(sed -n "s/^$name|//p" tests/expected-errors.txt)
    [ -n "$expected" ]
    status=0
    rm -f "$tmp/intent.json"
    python3 validate.py "$fixture" --emit-json "$tmp/intent.json" > "$tmp/validator.txt" || status=$?
    [ "$status" -eq 1 ] && [ -s "$tmp/intent.json" ]

    status=0
    output=$(yanglint -t config wic2005-intent.yang "$tmp/intent.json" 2>&1) || status=$?
    [ "$status" -ne 0 ]
    first=$(printf '%s\n' "$output" | sed -n '/^libyang err : /{p;q;}')
    case "$first" in
        *"$expected"*) printf '%s  %s\n' "$name" "$first" ;;
        *) printf 'Unexpected error for %s:\n%s\n' "$name" "$output" >&2; exit 1 ;;
    esac
done
printf '%s\n' 'All bad fixtures emitted JSON and hit their intended YANG rule.'
