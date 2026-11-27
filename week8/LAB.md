# Week 8 guided lab

Run the setup in [README.md](README.md#reproduce), then run `sh run_lab.sh` inside the container. The [transcript](evidence/lab.txt) includes the commands, diagnostics and exit statuses from Steps 0–7. The example VLAN module and starter data come from the [course starter](https://github.com/firdaussahran/wic2005/tree/93e2002c0c25e723e66332568d1fee42a17dcaf3/labs/week-08).

## Steps 0–2 · Tools, interfaces and augmentation

The run used Python 3.12.16, pyang 2.7.1 and yanglint 3.12.2 in the course's `python:3.12` container. `pyang -f tree` showed that the key of `interface* [name]` is `name`, so `/interfaces/interface[name='eth1']` selects the configured uplink. Examples of writable leaves are `description`, `type` and `enabled`. Examples of read-only leaves are `oper-status`, `if-index` and `phys-address`. The latter two depend on feature support or data availability as defined by the model. The `ethernetCsmacd` identity comes from `iana-if-type.yang` and derives from `iana-interface-type`.

The combined tree adds `ip:ipv4!` underneath each interface. The presence container marks that IPv4 is configured on that interface. `address* [ip]` is keyed by `ip`. The `subnet` choice permits a prefix length or a netmask, with netmask availability controlled by a feature. The `ip:` tree prefix denotes the augmenting module.

- Data path for the prefix length: `/interfaces/interface[name='eth1']/ietf-ip:ipv4/address[ip='10.1.1.1']/prefix-length`
- RESTCONF URI: `/restconf/data/ietf-interfaces:interfaces/interface=eth1/ietf-ip:ipv4/address=10.1.1.1/prefix-length`

RESTCONF uses the module name at the root and when crossing into `ietf-ip`. The list keys go after `=` and both values here use only unreserved URI characters. These paths identify the leaf containing `24` in the lab fixture. [RFC 8040 §3.5.3](https://www.rfc-editor.org/rfc/rfc8040.html#section-3.5.3)

## Step 3 · Interface data

The personalized [interfaces.json](interfaces.json) passed the configuration check with both interface models and the IANA identity module loaded. Each mutation below was made on a fresh copy and rejected. These are the first diagnostics and their relevant path suffixes.

| Mutation | First diagnostic | Path suffix under `/ietf-interfaces:interfaces` |
| --- | --- | --- |
| Prefix length `33` | Unsatisfied range | `/interface[name='eth1']/ietf-ip:ipv4/address[ip='10.1.1.1']/prefix-length` |
| Type `iana-if-type:ethernet` | Invalid identityref, identity missing | `/interface[name='eth1']/type` |
| Address `10.1.1.300` | Failed to convert IPv4 address | `/interface[name='eth1']/ietf-ip:ipv4/address/ip` |
| Remove `lo0`'s name | List instance missing key `name` | `/interface` |

For example, the out-of-range length also caused a missing `subnet` choice because the bad leaf could not satisfy that choice.

## Step 4 · Example VLAN module

Strict pyang returned 0 and the tree showed the writable VLAN and port lists and their read-only state. `vlans-good.json` passed. The following constraints rejected the other inputs.

| File | What yanglint reported | Constraint |
| --- | --- | --- |
| `vlans-bad-range.json` | VLAN ID `5000` out of range | [`range` on `vlan-id`](example-vlans.yang#L16) |
| `vlans-bad-name.json` | `Guest WiFi` failed the name pattern | [`pattern` on `name`](example-vlans.yang#L34) |
| `vlans-bad-voice.json` | Voice VLAN `20` needs a QoS priority | [`must` on `vlan`](example-vlans.yang#L25) |
| `vlans-bad-port.json` | `eth1` references missing VLAN `30` | [`leafref` path on `access-vlan`](example-vlans.yang#L72) |

## Steps 5–6 · Wi-Fi data and datastores

The [original Wi-Fi model](old/example-wifi.yang) passed strict pyang, and `wifi-good.json` was valid. The Staff network relies on the default `wpa3-personal` and needs a passphrase. Removing it failed the network-level `must`. Pointing Staff at VLAN 999 failed the required `leafref` because the loaded VLAN list has no matching ID.

The VLAN state fixture failed under `-t config` because it contains `member-count` and `oper-status`, but passed full-data validation. The Wi-Fi fixture with `clients: 12` showed the same behavior. The Wi-Fi configuration without `clients` belongs in a configuration datastore such as `<running>` or `<candidate>` if supported. A device's inventory of clients belongs in `<operational>`, where it appears with configuration that is in use. In the full-data check, the interface fixture lacked `admin-status`, `oper-status`, `if-index` and `statistics/discontinuity-time` for each interface with the features enabled by this run. [RFC 8342](https://www.rfc-editor.org/rfc/rfc8342.html)

## Step 7 · Model updates

The [submitted Wi-Fi revision](example-wifi.yang) adds optional `max-clients`. `pyang --check-update-from` returned 0. In independent scratch variants it rejected making `passphrase` mandatory and deleting `hidden`. Narrowing `passphrase` from 8–63 to 12–63 characters also breaks existing data, but pyang returned 0 for that variant. As a regression check, the same eight-character Staff passphrase passed the old model and failed the narrowed model under yanglint.

## Wrap up

1. **Interface identity.** An `identityref` names a value derived from `interface-type`. IANA can publish another derived interface identity in its own module without editing the interface leaf or its base schema. With an enumeration, the set of named values lives in the leaf's type definition.
2. **IPv4 augmentation.** The interface model can be implemented independently of the IP feature set. `ietf-ip` supplies IP structure, controls and state where an interface exists, and can evolve according to its own revision history.
3. **Configuration and state.** `interfaces.json` describes intent. The full-data check required the interface statuses, indices and counter discontinuity times recorded above. The device's interface implementation and instrumentation supply them.
4. **Two validators.** `pyang --strict` checks YANG syntax and schema rules such as type and path resolution. The bad values, missing keys and unsatisfied cross-node constraints in Steps 3–6 require a concrete instance document. `yanglint` loads both the schema and that data.
5. **Missed incompatibility.** The passphrase length tightening passed the update checker. Checking old, valid short-passphrase instances against the proposed new schema exposes the break, and reviewing the change against the YANG revision rules explains it. [RFC 7950 §11](https://www.rfc-editor.org/rfc/rfc7950.html#section-11)
