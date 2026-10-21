# get_sybers.cluster

Proxmox cluster-node automation for the Get-Sybers lab: Ceph
mesh/tuning/diagnostics, SDN zone/VNet setup, audit-logging enforcement, node
repository management, and storage-network configuration. These plays operate at
host-root level on PVE nodes and are the irreducible cluster-operations tier that
cannot run under a scoped service token. The same tier runs the Ludus server on
the master node: its credential store (an encrypted ZFS vault mirrored into
PocketBase), its API identities and keys, its local patches and packer plugins.

Licence: `AGPL-3.0-only` (see [`LICENSE`](LICENSE), declared in
[`galaxy.yml`](galaxy.yml)).

## Install

Releases are published to Ansible Galaxy by the Release workflow
([`.github/workflows/release.yml`](.github/workflows/release.yml)) when a GitHub
release is published:

```sh
ansible-galaxy collection install get_sybers.cluster
```

The collection also installs straight from this repository, which carries the
`galaxy.yml` manifest at its root — the form the Ludus node consumes
(`ludus ansible collection add https://github.com/Get-Sybers/proxmaxxing.git --global --force`):

```sh
ansible-galaxy collection install git+https://github.com/Get-Sybers/proxmaxxing.git
```

Consumers pin an exact version in their own `requirements.yml`, as a Galaxy
version or as a git source:

```yaml
---
collections:
  - name: https://github.com/Get-Sybers/proxmaxxing.git
    type: git
    version: v0.1.0
```

This collection's own runtime dependencies are pinned in
[`requirements.yml`](requirements.yml); the `galaxy.yml` bounds are what
[`scripts/upgrade_pins.py`](scripts/upgrade_pins.py) raises within.

## Contents

### Roles

| Role | Purpose |
| --- | --- |
| `cluster_preflight` | Admission gate every cluster play includes first: running as root, on a PVE cluster node, and (opt-in) a live admin Ludus API key in the environment. |
| `cluster_discover` | Read the live cluster (hardware, disks, pools, interfaces, guests, corosync, PVE storage/access/SDN objects, Ceph) and fill the inventory's As-Is records from it — proposal files or in place, configured values winning unless an overwrite is asked for; `--check --diff` is a drift report. |
| `cluster_ludus_install` | Stand up (optionally) and idempotently reconcile a Ludus server for this cluster: the SAFE `config.yml` keys (Ceph `raw` storage, cluster mode, SDN zone, reserved range) without ever touching `database_encryption_key`, stage the ROOT key, verify services. |
| `cluster_secrets` | Retrieve a secret from the house credential store (file or keychain backend) under `no_log`. |
| `cluster_pb_store` | PocketBase API mechanics for the credential store: superuser auth, collection ensure/verify, and record primitives, under `no_log`. |
| `cluster_ludus_auth` | A library of single-action Ludus auth/credential task files, chained by plays via `tasks_from` (fetch, prove at `/whoami`, persist, mint). |
| `cluster_ceph_orphan_sweep` | Reap orphaned Ceph RBD disks left on the pool by timed-out `qmdestroy` calls; previews by default. |
| `cluster_patch_ludus` | Re-apply local patches to stock Ludus files after a `ludus-server --update` reverts them; idempotent, marker-verified. |
| `cluster_patch_packer_iso` | Redirect stock Packer templates at ISOs already held on the build node instead of re-downloading them; gated on the ISO manifest by sha256. |
| `cluster_plugin_packer` | Reproduce the pinned Packer plugin state under `/opt/ludus` idempotently; never deletes. |
| `sysmon_linux` | Install, configure, and verify Sysmon for Linux on cluster nodes via a push-model supply-chain gate. |

Each role ships `meta/argument_specs.yml` (typed, described inputs),
`defaults/main.yml`, a `README.md` stating its contract, and Molecule coverage
under [`extensions/molecule/`](extensions/molecule) (see [Testing](#testing)).

### Modules

| Module | Purpose |
| --- | --- |
| `get_sybers.cluster.ceph_info` | Read-only Ceph cluster/OSD/pool facts for the discovery and diagnosis plays. |

### Filters

| Filter | Purpose |
| --- | --- |
| `get_sybers.cluster.config_merge` | Fill a configuration mapping from discovered values (configured values win), or overwrite it with them; keyed lists merge element-wise. |
| `get_sybers.cluster.config_drift` | List every discovered value the configuration lacks or contradicts. |
| `get_sybers.cluster.to_config_yaml` | Render a mapping in the block-style, insertion-ordered YAML the inventory files are written in. |

### Playbooks

The plays in [`playbooks/`](playbooks) decide which roles run on which hosts and
carry no configuration of their own. The node plays target the `proxmox_cluster`
group over SSH, or `proxmox_master` for the once-per-cluster steps; the
controller-side plays target the declared `localhost` and run on the master node,
where the Ludus API and the credential store live.

| Play | Runs on | Does |
| --- | --- | --- |
| `cluster-discover.yml` | every node | Read the live cluster and fill the As-Is records (`node.yml`, `cluster.yml`); drift report under `--check --diff`. |
| `cluster-node-repos.yml` | every node | The no-subscription PVE and Ceph apt repositories, the enterprise repository removed. |
| `cluster-node-upgrade.yml` | the master, then every node | Rolling full-upgrade with a reboot into the new kernel; the master is never rebooted by the play. |
| `cluster-storage-net.yml` | every node | Bring up and persist the fast storage links (Thunderbolt, copper) from `host_vars/<host>/storage_net.yml`. |
| `cluster-ceph-mesh.yml` | every node | Loopbacks and FRR OpenFabric over the fast links; the Ceph cutover onto the mesh only with `-e apply_ceph_mesh_cutover=true`. |
| `cluster-ceph-tuning.yml` | the master | Apply the pool replication policy and the OSD tuning from `group_vars/proxmox_cluster/ceph.yml`. |
| `cluster-ceph-diagnose.yml` | every node | Check the same values for drift, mon-store free space and mesh binding; `-e ceph_gate_strict=true` fails on CRIT. |
| `cluster-ceph-orphan-sweep.yml` | the master | Preview (default) or remove the RBD images a timed-out `qmdestroy` orphaned. |
| `cluster-sdn-zone.yml` | the master | Ensure the VXLAN SDN zone Ludus uses exists. |
| `cluster-sdn-setup.yml` | the master | The NAT and range VNets, the range users' ACLs, the master's NAT uplink. |
| `ludus-server-install.yml` | the master | Install (opt-in) and reconcile the Ludus server's SAFE `config.yml` keys for this cluster. |
| `cluster-audit-logging.yml` | the controller, then every node | Supply-chain gate for the auditd/Sysmon packages, then the auditd ruleset and Sysmon for Linux on every node. |
| `cluster-credentials-vault.yml` | the controller | Create or reset the encrypted ZFS vault; home its passphrase in PocketBase and the break-glass GitHub secret. |
| `cluster-vault-invariant.yml` | the controller | Assert the vault holds exactly the at-rest entries the inventory lists. |
| `cluster-vault-migrate.yml` | the controller | Migrate the vault's service secrets into the PocketBase credential store. |
| `cluster-dek-rotate.yml` | the controller | Rotate Ludus's `database_encryption_key` and re-encrypt every record under it. |
| `cluster-token-restore-from-pve.yml` | the controller | Restore a Ludus user's PVE token secret from `token.cfg` under the current DEK. |
| `cluster-pb-credentials-setup.yml`, `cluster-pb-credential-read.yml` | the controller | Ensure the credentials collection with its API rules; read and verify records through the sanctioned path. |
| `cluster-identity-provision.yml` | the controller | Ensure the admin seats (`Cluster-Admin`, `Infra-Admin`) exist in Ludus. |
| `cluster-ghost9-pve-token.yml` | the controller | Mint the scoped `@pve` deploy token for the ghost9 range CT, its ACL-anchor pool and ACLs; home it in PocketBase; emit the deploy vars. |
| `ludus-ra-auth.yml`, `ludus-key-rotate.yml` | the controller | Prove an identity's stored key end to end and arm the `ludus` CLI; mint a new key and home it in PocketBase. |
| `ensure-default-sources.yml` | the controller | Register the default Ludus role/collection sources for the owner identity and purge retired ones. |
| `packer-iso-redirect.yml` | the controller | Make ISOs the build node already holds discoverable to the packer templates (report, then link). |
| `post-update-reconcile.yml` | the controller | After `ludus-server --update`: re-apply the local patches, the packer plugins and the pool ACLs. |

### Configuration

Every site-specific value — hosts, addresses, pools, zones, pins, paths — lives
in [`inventory/`](inventory/README.md) (`group_vars/<group>/<topic>.yml`,
`host_vars/<host>/<topic>.yml`), which `ansible.cfg` points at so no `-i` is
needed. The repository carries only the template of that configuration,
[`inventory/example/`](inventory/example); `make config` copies it into
`inventory/` and the copies are untracked, so no node name, subnet, pool or
serial is ever committed. The template's contract: the nodes are `pi-01`,
`pi-02` and `pi-03` (`pi-01` the master), addresses are RFC 5737 documentation
addresses (`192.0.2.0/24` the management LAN, `198.51.100.0/24` the Ceph mesh,
`203.0.113.0/24` the point-to-point storage links), and every value an operator
must set is `CHANGE-ME`. PVE API auth comes from the `PROXMOX_*` environment
variables ([`proxmox_api.yml`](inventory/example/group_vars/all/proxmox_api.yml)).

Two records are *discovered* rather than written by hand —
`host_vars/<host>/node.yml` and `group_vars/proxmox_cluster/cluster.yml`. The
template ships them as skeletons and
[`playbooks/cluster-discover.yml`](playbooks/cluster-discover.yml) fills them
from the live cluster:

```sh
ansible-playbook playbooks/cluster-discover.yml                  # proposal files under inventory/discovered/
ansible-playbook playbooks/cluster-discover.yml --check --diff   # drift report, nothing written
ansible-playbook playbooks/cluster-discover.yml -e cluster_discover_write=in_place [-e cluster_discover_overwrite=true]
```

Configured values win by default (discovery only fills what is missing);
`cluster_discover_overwrite=true` lets the live values win while keeping the
annotations a node cannot report. `cluster_discover_strict=true` turns the play
into a gate that fails on any difference.

### The LXC tier

The hardened containers that run on the cluster — today the self-hosted 1Password Connect server and the credential mirror into it — are
not part of this collection. They live in [get-sybers/lxc](https://github.com/get-sybers/lxc) (`get_sybers.lxc`), which owns both the build
of every container and every sanctioned way of interacting with one (its API, or its own roles over `pct exec`). This tier supplies what it
needs: a node, a Debian template, a bridge, and an admin PVE API credential in the `PROXMOX_*` environment.

### Documentation

[`doc/index.md`](doc/index.md) is the entry point: [how-to guides](doc/howto/index.md) (configure and discover a cluster, run the plays
from the controller container, the Ludus server, keys and patches), [reference](doc/reference/index.md) (the inventory contract, the roles,
the plugins, the Proxmox LDAP/AD authentication notes) and the house [standards](doc/standards/02-Ansible-Standards.md) (the Ansible
standard, the CI workflow, linting and conformance).

## Repository layout

```text
.
├── doc/                  # documentation: index.md, howto/, reference/, standards/
├── roles/                # cluster_preflight, cluster_discover, cluster_ludus_install, cluster_secrets, cluster_pb_store,
│                         # cluster_ludus_auth, cluster_ceph_orphan_sweep, cluster_patch_ludus, cluster_patch_packer_iso,
│                         # cluster_plugin_packer, sysmon_linux
├── plugins/              # the ceph_info module and the config_merge, config_drift, to_config_yaml filters
├── playbooks/            # cluster-*, ludus-*, ensure-default-sources, packer-iso-redirect, post-update-reconcile
├── inventory/            # the single config home: example/ (the template), secrets/ (vaulted -e files)
├── meta/                 # runtime.yml, the ISO manifest, the Ludus stock pins
├── container/            # the controller image (Containerfile, run.sh)
├── extensions/molecule/  # the test scenarios and their Debian substrate
├── tests/unit/           # unit tests for the plugins
├── scripts/              # check_pins, upgrade_pins, molecule_lanes
├── changelogs/           # antsibull-changelog fragments and the generated changelog
├── galaxy.yml            # the collection manifest
├── Makefile              # make conform: the local gate CI runs
├── AUTHORS, MAINTAINERS, CONTRIBUTING.md, CODE_OF_CONDUCT.md, SECURITY.md, LICENSE
└── .github/              # workflows (CI, Release, Links, Update pins, Scorecard), rulesets, issue and PR templates
```

## Development

```sh
make config      # copy the configuration template into inventory/ (untracked), then replace every CHANGE-ME
make deps        # install pinned collections + test tooling
prek install     # git hooks (lint, secrets, commit-msg)
make conform     # the full local gate: lint, pins, sanity, molecule, changelog, build
make upgrade     # raise every pin to its galaxy.yml ceiling, then re-run conform
```

[`container/`](container/README.md) builds a reproducible controller image that runs the SSH-based cluster plays,
`--syntax-check` and lint without a workstation install of ansible-core and the collections.

### Testing

Molecule drives every role against a throwaway, digest-pinned Debian 13
container (the `community.docker` driver — PVE is Debian), configured once in
[`extensions/molecule/config.yml`](extensions/molecule/config.yml); each scenario
overrides only its own playbooks. The container is disposable test scaffolding —
it is not a Proxmox node and never touches the cluster.

- **A negative scenario for every role** (`*_negative`): run without the role's
  live dependency, each role must stop at its own labelled assertion — never
  crash or silently proceed. These run hermetically in CI.
- **A positive scenario where the host-side logic is self-contained**
  (`default` → `cluster_secrets`; `discover` → `cluster_discover`'s merge, write
  and drift semantics against a committed fixture): seed the fixture, converge,
  then assert the outcome and idempotence.
- **Roles that mutate a live PVE/Ceph/Ludus/PocketBase** keep their positive path
  on a real node (the plays themselves) rather than a faked container; the
  container tier proves their refusal/guard behaviour, and
  `ansible-lint --profile production` covers the rest.

Run the whole suite with `make molecule` (`molecule test --all`), or one scenario
with `molecule test -s <scenario>`. Collections resolve from the single-source
[`requirements.yml`](requirements.yml), installed by `make deps` first. The
plugins' unit tests run under `make unit` (tox-ansible).

### CI lanes

The pull-request workflow runs only what a change can affect.
[`scripts/molecule_lanes.py`](scripts/molecule_lanes.py) reads the diff and
decides: a docs-only change skips the collection gate and molecule; a role
change runs the scenarios that drive that role (found by following the
`get_sybers.cluster.<role>` references, so a change to `cluster_preflight`
runs every scenario that includes the gate); a change to anything the
scenarios share (the molecule base config and Dockerfile, `plugins/`, the
collection metadata and pins, the workflow) runs them all, fanned out over
parallel lanes. Push to `main`, the nightly schedule and a manual dispatch
always run everything, so a wrong lane can hide a failure for at most a day.
See the plan for your branch before pushing:

```sh
python3 scripts/molecule_lanes.py --event pull_request --base origin/main --head HEAD
```

Every change that touches a plugin needs a fragment in
[`changelogs/fragments/`](changelogs/fragments). Releases follow standard 04:
merge the changelog, publish a GitHub release tagged `v<galaxy.yml version>`,
and the Release workflow publishes that version to Ansible Galaxy.
