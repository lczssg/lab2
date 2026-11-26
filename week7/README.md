# WIC2005 Week 7 Lab and assignment

The intent describes a campus media lab on `10.1.0.0/16` for student ID suffix `6101` (`NN=1`). It manages six VLANs and four ordered ACL entries. The rules block guests from the equipment administration network and allow specific HTTPS, DNS and SSH traffic between the other VLANs. The lab API retains its reserved VLAN 1. [Week 7 lab and assignment brief](https://firdaussahran.github.io/wic2005/weeks/week-07/#lab)

## Run it in two containers

From the repository root, use a Bash-compatible shell with Docker. Download the two unmodified course files into `week7/` before starting the containers. The session below uses the API's Docker DNS name, `api`. Use separate names if `api`, `client` or `apilab` are already in use.

```bash
cd week7
curl -fsS https://raw.githubusercontent.com/firdaussahran/wic2005/main/labs/week-07/labapi.py -o labapi.py
curl -fsS https://raw.githubusercontent.com/firdaussahran/wic2005/main/labs/week-07/retry_naive.py -o retry_naive.py
docker network create apilab
docker run -d --name api --network apilab -v "${PWD}:/lab:ro" -w /lab python:3.12 python3 labapi.py --id 6101
docker logs api
docker run -it --rm --name client --network apilab -v "${PWD}:/lab" -w /lab python:3.12 bash
```

In the client container, enter the course-provided lab credentials when prompted. The captured runs used Python 3.12.16, Requests 2.34.2 and PyYAML 6.0.4.

```bash
python3 -m pip install -r requirements.txt
read -r -p 'Lab username: ' LAB_USERNAME
read -rs -p 'Lab password: ' LAB_PASSWORD; printf '\n'
export LAB_USERNAME LAB_PASSWORD
export LAB_API_URL=http://api:8000
python3 sync.py intent.yaml --dry-run
python3 sync.py intent.yaml
python3 sync.py intent.yaml
```

For E3, start a fresh API before the dry run, before the chaos apply, and before the expiry run. Leave the client container open during API restarts. Use `docker rm -f api` from a second host terminal and repeat the API `docker run` command from `week7/`. Append `--token-ttl 3 --rate 2` to that command for the expiry run. Wait for the startup message in `docker logs api` before each scenario. For the guided inventory expiry test, use `--token-ttl 5 --rate 2` instead.

```bash
# From the client, after restarting the API for the chaos apply.
curl -fsS -X PUT "$LAB_API_URL/api/v1/lab/chaos" \
  -H 'Content-Type: application/json' -d '{"lose_responses":0.3,"errors_503":0.2}'
python3 sync.py intent.yaml
curl -fsS "$LAB_API_URL/api/v1/lab/audit"
python3 sync.py intent.yaml  # Keep the same API instance and chaos settings.
curl -fsS "$LAB_API_URL/api/v1/lab/audit"
```

For a separate readback after the chaos apply, use a fresh bearer in the same client shell. `curl --retry` lets the evidence reads recover from a transient 503 or 429.

```bash
TOKEN=$(python3 - <<'PY'
import os
import requests

url = os.environ['LAB_API_URL'] + '/api/v1/auth/token'
credentials = {'username': os.environ['LAB_USERNAME'], 'password': os.environ['LAB_PASSWORD']}
reply = requests.post(url, json=credentials, timeout=5)
reply.raise_for_status()
print(reply.json()['token'])
PY
)
curl -fsS --retry 6 -H "Authorization: Bearer $TOKEN" "$LAB_API_URL/api/v1/vlans"
curl -fsS --retry 6 -H "Authorization: Bearer $TOKEN" "$LAB_API_URL/api/v1/acl/entries"
unset TOKEN
```

`python3 inventory.py` follows the device pages and writes the local `devices.json`. For the guided retry exercise, obtain `LAB_API_TOKEN` from the course login endpoint in the client shell, then run `python3 retry_naive.py 6101` and `python3 retry_safe.py 6101` against the exercise instance. The course lab tab contains the curl steps and chaos settings. Exit the client and remove the API and network you created after the lab. [Guided lab](https://firdaussahran.github.io/wic2005/weeks/week-07/#lab)

## Guided lab results

**Docker network.** `docker network inspect apilab` showed a bridge on `172.19.0.0/16`, with the API at `172.19.0.2/16` and the client at `172.19.0.3/16` in this run. Each has its own network namespace. A veth pair connects each container namespace to the Linux bridge, and Docker DNS resolves the API's name on that network. The lab's `10.1.0.0/16` device inventory and ACL addresses are data served by the API. [Network evidence](lab7/network.txt)

**HTTP results.** The unauthenticated request got `401` with `WWW-Authenticate: Bearer`, and the authenticated request got `200` with `Content-Type: application/json`. Five of ten rapid reads succeeded, followed by five `429` replies. [HTTP transcript](lab7/status.txt)

| Status | Client action |
| --- | --- |
| 400 | Repair malformed JSON before sending it again. |
| 403 | Stop and use an account authorised for the write. Logging in again as the viewer keeps the same role. |
| 404 | Check the URL or handle an absent resource. On a planned DELETE, absence fulfills the operation. |
| 405 | Consult `Allow` and use a supported method. |
| 409 | Re-read or resolve the conflict. VLAN 10 already exists, so a planned replacement uses PUT on its URL. |
| 422 | Correct the payload. VLAN 5000 is out of range. |
| 429 | Wait the number of seconds in `Retry-After`, then resend a safe request. |

The client never retries unchanged requests on 400, 403, 404, 405, 409 or 422. An expired bearer token on a resource request prompts a login and a retry. A login failure stops the run.

**Idempotency and lost replies.** Both PUTs for VLAN 30 left the same name (`201`, then `200`). Both DELETEs for VLAN 99 left it absent (`204`, then `404`). Two bare POSTs made two ACL entries. Two POSTs with the same key and body returned `201` twice, with `Idempotent-Replayed: true` on the second response and one new entry in the audit. At 50% response loss, the fifth naive run created two entries after its first reply was lost. The safe run also lost its first reply, then got a replay and added exactly one entry. `retry_safe.py` creates the key before sending the first request so the server can recognize the retry even if the first reply never arrives. [Step 3](lab7/audit-step3.txt) · [Step 4](lab7/audit-step4.txt)

**Inventory.** Page size 10 required 21 successful pages for 201 devices, matching `X-Total-Count`. With 20% injected 503s, the total was 29 requests, including the initial login, five 503s and two 429s. With a five-second token and two requests per second, the total was 36, including three logins, ten 429s and two expired-token 401s. The inventory contained 51 devices at `kl-hq` and 50 at each of `johor`, `penang` and `pj-dc`. [Inventory run](lab7/inventory.txt) · [Inventory expiry run](lab7/expiry.txt)

**OpenAPI.** The maximum device page size is 50. The document lists GET and DELETE on `/api/v1/acl/entries/{id}`. Reusing an idempotency key with a different body gives 422. The `site` filter was the new discovery. `GET /api/v1/devices?site=pj-dc&limit=50` returned all 50 devices at `pj-dc` on one page with `next: null`. [OpenAPI checks](lab7/openapi.txt)

## Assignment evidence

| Run | Observed result |
| --- | --- |
| [Dry run](evidence/dry-run.txt) | Fresh API. Eleven planned changes. The audit and request log show zero configuration writes. |
| [Apply under chaos](evidence/apply.txt) | 30% response loss and 20% 503s configured. The run handled 429, 503 and lost replies, including a replayed ACL POST. Eleven mutations were audited. Independent GETs returned the six intended VLANs plus VLAN 1 and four unique ACLs in the intended order. |
| [Second run under the same chaos](evidence/second-run.txt) | Empty plan on the same API after apply. Audit stayed at eleven, and the server request log shows zero configuration write requests. |
| [Assignment token expiry](evidence/expiry.txt) | Fresh API, token TTL 3 s, rate 2/s. Two expired-token 401s triggered logins and the run converged. Independent GETs and the eleven audit entries confirmed the result. |

## E4 answers

### How the plan is built

`sync.py` validates the YAML before reading both collections using `Client.get_all()`. VLANs are compared by ID and name. VLAN 44 was missing, so its planned PUT created `capture-studios`. VLAN 10 was present as `users`, so its PUT renamed it to `editing-stations`. VLAN 99 had no desired row, so the client deleted it. VLAN 1 is reserved and left outside the managed comparison.

For ACLs the API returns entries in ID order and POST appends to that order. The planner compares the user-controlled fields with the API defaults filled in. It keeps the longest prefix of the desired sequence that occurs in order in the API, deletes unneeded entries by their server IDs, and appends the remaining desired entries. The fresh ACL was empty, so the first append added `guests-blocked-from-admin` from `10.1.30.0/24` to `10.1.70.0/24`. After applying the plan, the client reads both collections again and requires an empty difference. The second run can carry out the same verification with configuration reads alone.

### Which requests can be retried

| Request | Retry behavior |
| --- | --- |
| GET of VLANs or ACLs | Read-only. Retrying the same page leaves the resources unchanged. |
| PUT of a VLAN ID | The same name is written to the same ID each time. A lost create response can turn a later return code from 201 into 200 while preserving the same final state. |
| DELETE of a VLAN or ACL ID | A repeat leaves the same ID absent. A 404 completes this intended outcome. |
| POST to append an ACL entry | The same `Idempotency-Key` and body are reused for that planned append. The API can replay the first result without creating a duplicate. |
| POST to obtain a token | This call has no automatic retry. If login fails, the script exits. A 401 on a resource call can initiate a fresh login. |

For resource calls, 429 waits the seconds in `Retry-After`. For 503, connection loss or timeout, the client backs off from one second, doubles the wait and adds jitter. It stops on the sixth transient failure or the sixteenth resource attempt, whichever is reached first. Other unexpected HTTP errors fail the run. A failed run may have applied some changes. A later invocation starts with fresh reads and recomputes the plan.

### Why ACL POST needs a key

The VLAN ID gives PUT a stable target. For ACLs the server assigns IDs, so every planned append gets a fresh UUID once, immediately before its first attempt. The HTTP retries and any token refresh use that same UUID and body. A new UUID on each attempt could cause a duplicate after a lost response. Reusing a UUID for a different rule can give 422. Reusing an old UUID when intentionally adding the same rule after deletion can return a cached 201 for an entry that no longer exists. A normal second run has no planned append and therefore generates no key.

### Concurrent runs

Two clients can read the same starting state and interleave their plans. A later VLAN PUT can overwrite an earlier one. Two clients can also append competing or duplicate ACL entries with distinct keys. A readback can spot a mismatch at the time of verification. The lab API serialises individual requests but provides no transaction across the plan. Safe concurrent writers would need an atomic configuration update with a revision precondition covering both collections, or a server-enforced lock spanning the read, apply and verification. Per-resource ETags could detect individual stale writes. They would still allow partial application of a plan.

### Credentials

The password is entered into the local client shell and exported with `LAB_USERNAME`. The bearer issued by the server lives in the client object's memory. The scripts print statuses, request paths and results without printing the password or bearer. The course server and naive example are downloaded locally. This folder ignores them, the generated device inventory and `.env`. The committed Week 7 files and their revisions were checked for demo passwords, bearer values, credential patterns and a full student ID.

## AI use

The published brief permits Level 3 (Open) AI use. OpenAI Codex checked the official brief and starter, proposed the campus-media VLAN and ACL intent, completed `inventory.py`, and wrote `retry_safe.py` and `sync.py`. It ran the steps and four assignment cases against the course API in Docker, captured and checked the evidence, and drafted this README and the local Appendix 2(b) draft. The experiment logs record the observed API behavior. [Official Week 7 AI instructions](https://firdaussahran.github.io/wic2005/weeks/week-07/#assignment--make-the-api-match-your-intent)
