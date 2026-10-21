# Containerized Ansible controller

Run the `get_sybers.cluster` plays from a reproducible Debian controller instead
of installing ansible-core, the Galaxy collections, and their Python SDKs onto
your Mac. Built for [Apple `container`](https://github.com/apple/container)
(macOS 15+/26+), but the `Containerfile` is plain OCI and builds under Docker or
Podman unchanged.

## What's in the image

| Layer | Pinned by |
| --- | --- |
| Debian trixie base (same digest as the molecule substrate) | `Containerfile` `DEBIAN_BASE` arg |
| `ansible-core` (2.21 by default) | `Containerfile` `ANSIBLE_CORE` arg |
| `community.general`, `ansible.posix`, `community.proxmox` | [`../requirements.yml`](../requirements.yml) |
| `proxmoxer`, `requests`, `ansible-lint`, `yamllint` | [`requirements-runtime.txt`](requirements-runtime.txt) |

The collections are baked from `requirements.yml` — the repo's single source of
pinned versions — so the image resolves identically to a `make deps` host setup.

## One-time setup

```bash
# 1. install Apple container (Intel is unsupported; Apple silicon only)
#    https://github.com/apple/container/releases
# 2. start its background service
container system start
```

## Usage

The collection checkout (the repository root) is bind-mounted into the
container, so edits are picked up with no rebuild. All commands run from
`container/`:

```bash
./run.sh                                                   # interactive shell
./run.sh ansible-playbook playbooks/cluster-ceph-diagnose.yml -i inventory/
./run.sh ansible-playbook playbooks/cluster-storage-net.yml  -i inventory/ --check --diff
./run.sh ansible -m ping all -i inventory/                 # SSH reachability
./run.sh ansible-lint playbooks/                           # lint the tree
./run.sh ansible-playbook --syntax-check playbooks/cluster-ceph-mesh.yml -i inventory/
```

First run builds the image (a few minutes); later runs are layer-cached and
near-instant. `SKIP_BUILD=1 ./run.sh …` skips the build check entirely.

## Credentials and SSH

- `~/.ssh` is mounted **read-only**. Key-based auth to the nodes works as-is, and
  because you already SSH to these hosts they're in `known_hosts`, so host-key
  checking stays on with nothing to write. A brand-new host needs one `ssh` from
  the Mac first (or export `ANSIBLE_HOST_KEY_CHECKING=false`).
- SSH **agent** forwarding is not wired up; use key files, or an unencrypted key,
  or add agent support if your keys are passphrase-protected.
- These shell vars are forwarded when set: `PROXMOX_HOST`, `PROXMOX_USER`,
  `PROXMOX_TOKEN_ID`, `PROXMOX_TOKEN_SECRET`, `PROXMOX_PASSWORD`, and `ANSIBLE_*`.

## Networking caveat — the localhost plays

The container reaches the PVE nodes over the management LAN (SSH), so the
node-targeting plays (`hosts: proxmox_cluster` / `proxmox_master` — Ceph, SDN,
storage net, audit install, node repos/upgrade) run fine here.

The credential/vault plays run `hosts: localhost` and talk to Ludus/PocketBase on
`https://127.0.0.1:8080`. Inside the container `127.0.0.1` is the container, **not**
a PVE node, so those plays are meant to run **on the master node** or over an SSH
tunnel — not from this controller as-is. Use the container for the SSH-based
cluster plays, `--syntax-check`, and lint.

## Not a test harness

This image runs plays and lints. The `make sanity` / `make molecule` matrices
need tox + the molecule Docker driver and are a separate concern — keep running
those via `make` on a host with Docker.
