#!/bin/sh
set -eu
cd "$(dirname "$0")"
M=/usr/local/share/yang/modules

printf '%s\n' '$ pyang --strict wic2005-intent.yang'
pyang --strict wic2005-intent.yang
printf '%s\n' '$ pyang -P "$M/ietf" --check-update-from old/wic2005-intent.yang wic2005-intent.yang'
pyang -P "$M/ietf" --check-update-from old/wic2005-intent.yang wic2005-intent.yang
printf '%s\n' 'COMPATIBLE (exit=0)' ''

printf '%s\n' '$ pyang -P "$M/ietf" --check-update-from old/wic2005-intent.yang scratch/wic2005-intent.yang'
status=0
diagnostic=$(pyang -P "$M/ietf" --check-update-from old/wic2005-intent.yang scratch/wic2005-intent.yang 2>&1) || status=$?
printf '%s\n' "$diagnostic"
[ "$status" -eq 1 ]
printf '%s\n' "$diagnostic" | grep -q 'range has been illegally restricted'
printf 'INCOMPATIBLE (exit=%s)\n' "$status"
