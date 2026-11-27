# Week 8 · Give your intent a schema

The campus media lab intent (student suffix `6101`) declares six managed VLANs and four ordered ACL entries in `10.1.0.0/16`. It comes from [the Week 7 submission](../week7/intent.yaml). The [guided lab notes](LAB.md) cover Steps 0–7 and the five wrap-up answers. [Official Week 8 brief](https://firdaussahran.github.io/wic2005/weeks/week-08/#assignment--give-your-intent-a-schema)

## Reproduce

From `week8/` in Bash with Docker, use the course's `python:3.12` setup. The container names below are used only for this experiment.

```sh
docker run -dit --name wic2005-week8-yanglab -v "$PWD:/lab" -w /lab python:3.12
docker exec wic2005-week8-yanglab sh -c \
  'pip install pyang==2.7.1 -r requirements.txt && apt-get update && apt-get install -y libyang3-tools'
docker exec wic2005-week8-yanglab sh run_lab.sh
docker exec wic2005-week8-yanglab sh run_tests.sh
docker exec wic2005-week8-yanglab sh check_diagnostics.sh
docker exec wic2005-week8-yanglab sh check_update.sh
docker exec wic2005-week8-yanglab python3 validate.py intent.yaml --emit-json /tmp/intent.json
```

For the isolated API checks, download the official Week 7 `labapi.py` to a separate starter directory and mount it read-only. The commands below assume Bash and are run from `week8/`. Set `LAB_USERNAME` and `LAB_PASSWORD` in your shell using the course's lab credentials before the credentialed commands. The isolated network alias is `api`.

```sh
starter=$(mktemp -d)
curl -fsS https://raw.githubusercontent.com/firdaussahran/wic2005/93e2002c0c25e723e66332568d1fee42a17dcaf3/labs/week-07/labapi.py \
  -o "$starter/labapi.py"
docker network create wic2005-week8-net
docker run -d --name wic2005-week8-api --network wic2005-week8-net \
  --network-alias api -v "$starter:/lab:ro" -w /lab \
  python:3.12 python3 -u labapi.py --id 6101
docker network connect wic2005-week8-net wic2005-week8-yanglab

docker logs wic2005-week8-api
docker exec -e LAB_USERNAME -e LAB_PASSWORD wic2005-week8-yanglab \
  python3 sync.py tests/bad-vlan-4095.yaml --dry-run
docker logs wic2005-week8-api
docker exec wic2005-week8-yanglab env -u LAB_USERNAME -u LAB_PASSWORD \
  python3 sync.py tests/bad-vlan-4095.yaml --dry-run
docker logs wic2005-week8-api
docker exec -e LAB_USERNAME -e LAB_PASSWORD wic2005-week8-yanglab \
  python3 sync.py intent.yaml --dry-run
docker logs wic2005-week8-api

docker exec -e LAB_USERNAME -e LAB_PASSWORD wic2005-week8-yanglab python3 -u run_api_checks.py
docker rm -f wic2005-week8-yanglab wic2005-week8-api
docker network rm wic2005-week8-net
rm -f "$starter/labapi.py"
rmdir "$starter"
```

Use a fresh API for `run_api_checks.py`. It compares the write audit and applies the intent, including deleting the seeded VLAN 99. The API keeps its data in memory. The course starter and credential values are available from the [Week 7 lab](https://firdaussahran.github.io/wic2005/weeks/week-07/).

## G1–G4 results

- **Model.** [wic2005-intent.yang](wic2005-intent.yang) passed `pyang --strict`. VLAN entries are keyed by ID and ACL entries by description. YANG keys make the values required and unique within each list. The ACL list preserves user order, because the Week 7 API appends rules in evaluation order. The derived prefix type requires an IPv4 prefix in `10.1.0.0/16` with length 16–32. Container-level `must` statements enforce a permit, a deny and a port. The port leaf applies only when the protocol is TCP or UDP. Omitted protocol defaults to `any`.
- **Gate.** `validate.py` wraps the parsed YAML in its namespaced JSON container and optionally writes that JSON before invoking yanglint. `sync.py` validates the same parsed data that it will use, then constructs the API client. It retains Week 7's resource comparison, ordered ACL updates, retry behavior and read-back check. The Week 7 HTTP helper is included unchanged so the folder can run on its own.
- **Tests.** Both good files passed and 26 bad files failed. Each bad file was emitted as JSON and independently passed to yanglint. The first diagnostic matched the intended rule in all 26 cases. The invalid dry runs exited 1 with and without credentials, printed no plan and left the isolated server's request count at zero. A valid dry run then produced three logged HTTP requests: authentication and the two state reads. The valid dry run planned 11 changes and the API audit stayed at zero. The apply made 11 audited writes and converged on 6 managed VLANs and 4 ACL entries in order. VLAN 1 was preserved. Applying a second time planned zero writes. [Suite](evidence/tests.txt) · [full diagnostics](evidence/diagnostics.txt) · [gate](evidence/gate.txt) · [API](evidence/api.txt)
- **Evolution.** The [old module](old/wic2005-intent.yang) is preserved. Revision 2 adds optional ACL leaf `log` and accepts the unmodified Week 7 input, as well as an input that uses the new leaf. The official API has no logging preference field, so the reconciliation payload still uses its existing fields. The [scratch copy](scratch/wic2005-intent.yang) raises the VLAN minimum ID from 2 to 11. pyang accepted the optional addition and flagged the restricted range. [Revision evidence](evidence/update.txt)

## G5 analysis

1. **Network address semantics.** The derived type checks that the prefix is syntactically IPv4 and stays within the assigned /16. Requiring the original text to have zero host bits for every prefix length would be awkward to encode in a portable YANG pattern or XPath expression. For the specific test, `validate.py --emit-json` preserved `10.1.40.5/24`, yanglint accepted it and printed the canonical value `10.1.40.0/24`, and the official API returned HTTP 422 when sent the original string. The API uses strict network parsing and returns a field-specific description. Strict enforcement can live at the write endpoint, where the server has the original input and applies the same behavior to all clients. A validated intent can still encounter this API rejection, since the sync carries the original prefix and uses independent API calls. [API transcript](evidence/api.txt)
2. **One model for the class.** Put allocations in a trusted owner table with a key per student and an assigned prefix. Reference the allocation from each intent. For this course's fixed /16 scheme, store the trusted second octet and compare the first two octets against it with a `must` expression after enforcing the minimum prefix length. For arbitrary prefix lengths, look up the authenticated owner's allocation and check subnet containment in the controller. The authenticated identity and allocation both come from the server.
3. **Read-only Week 7 data.** The inventory's reported `os_version`, the server-assigned ACL entry `id`, and the audit entry's server-recorded `time` would be `config false` leaves in an equivalent YANG model.
4. **VLAN errors.** The observed 422 for ID 4095 returned an `error` string saying the API's valid range was 1–4094. A model-aware error could identify the rejected YANG leaf (for example `/wic2005-intent:intent/vlans/id`), use a machine-readable `invalid-value` tag, and report this intent's range of 2–4094. The client could then highlight the exact field and distinguish a range problem from a missing key or a bad name. [API transcript](evidence/api.txt) · [RFC 8040 §3.9](https://www.rfc-editor.org/rfc/rfc8040.html#section-3.9)
5. **Client compatibility.** Raising the VLAN minimum would reject VLAN 10 in our existing intent before any sync. Other clients with VLANs 2–10 would hit the same break. The submitted revision only adds an optional leaf. Older intents still validate and the client continues to send the same API fields.
6. **Measured values.** A measured round-trip time is reported state. Add a `config false` leaf with a numeric type and a unit, such as milliseconds, and read it from the NMDA `<operational>` datastore. The system performing the measurement supplies the value. [RFC 8342](https://www.rfc-editor.org/rfc/rfc8342.html)

## AI use

The official brief permits Level 3 (Open). OpenAI Codex reviewed the official starter and the prior submission, implemented the Wi-Fi and intent models, adapted `validate.py` and `sync.py`, and prepared the fixtures and reproduction scripts. It ran the Docker experiments and checks, recorded the tool and API output, and drafted these notes and the local Appendix 2(b). The tested configuration and network results are traceable to the fixtures and transcripts in this folder. [Official AI use conditions](https://firdaussahran.github.io/wic2005/weeks/week-08/#assignment--give-your-intent-a-schema)
