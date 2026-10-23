#!/bin/sh
# Run inside the isolated course container from /lab. Existing evidence is replaced.
set -eu
mkdir -p evidence3 week3
python3 test_week3.py > evidence3/model-check.txt 2>&1
if python3 build_routed.py loop.yaml > evidence3/check.txt 2>&1; then
    echo 'ERROR: loop.yaml was accepted' >&2
    exit 1
fi
if python3 build_routed.py missing.yaml >> evidence3/check.txt 2>&1; then
    echo 'ERROR: missing.yaml was accepted' >&2
    exit 1
fi
python3 routers.py --id 6101 < commands/week3-guided.txt > week3/guided-session.txt 2>&1
if python3 routers.py --id 6101 --routes week3/loop-routes.yaml > week3/check-loop.txt 2>&1; then
    echo 'ERROR: guided loop was accepted' >&2
    exit 1
fi
if python3 routers.py --id 6101 --routes week3/missing-routes.yaml > week3/check-missing.txt 2>&1; then
    echo 'ERROR: guided missing route was accepted' >&2
    exit 1
fi
python3 routers.py --id 6101 --routes routes.yaml < commands/week3-guided-data.txt > week3/data-session.txt 2>&1
python3 build_routed.py network.yaml < commands/week3-assignment.txt > evidence3/session.txt 2>&1
echo 'Collected model checks, guided exercises, and assignment network evidence.'
