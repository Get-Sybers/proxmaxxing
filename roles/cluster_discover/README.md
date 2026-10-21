# cluster_discover

Reads the live Proxmox cluster and fills the inventory's **As-Is records** from it: `host_vars/<host>/node.yml` (one per node) and
`group_vars/<group>/cluster.yml` (one per cluster). It is the mechanism that keeps the configuration honest about what exists without anyone
typing hardware, addresses, guests or Ceph topology by hand. The inventory stays the single place that holds this information; the role only
fills or refreshes it.

## What it gathers

| Record | Source on the node | Keys |
| --- | --- | --- |
| `node` | `pvesh get /version`, `/cluster/config/nodes`, `lsblk`, `zpool list`, `ip -j -d addr`, `/nodes/<node>/qemu` and `/lxc`, the `min`/`hardware`/`network` facts | `name`, `mgmt_ip`, `corosync_id`, `quorum_votes`, `pve_version`, `kernel`, `hardware` (`cpu`, `cpus`, `mem_total_mb`), `disks[]` (`dev`, `size`, `model`, `serial`, `transport`, `rotational`), `zfs_pools[]` (`name`, `size`, `cap`, `health`), `ceph` (`roles`, `mon_addr`, `osds`), `network{}` (per interface: `ip`, `type`, `mtu`, `state`, `ports`), `guests` (`templates[]`, `vms[]`, `cts[]` with `id`, `name`, `status`) |
| `cluster` (once) | `pvesh get /cluster/status`, `/cluster/config/join`, `/storage`, `/access/*`, `/pools/*`, `/cluster/sdn/*`, `/cluster/mapping/dir`, `get_sybers.cluster.ceph_info` | `name`, `config_version`, `quorate`, `fingerprint`, `nodes[]`, `ceph` (`fsid`, `release`, `version`, `health`, networks, `mon_host`, pool defaults, `mons[]`, `osds`, `pools[]`), `storage[]`, `users`, `groups`, `pools[]`, `roles`, `realms[]`, `sdn` (`zones`, `vnets`, `subnets`, `controllers`, `ipams`, `fabrics`), `directory_mapping[]` |

Every read is a read-only probe (`changed_when: false`, runs under `--check`). Nothing on the node is modified; the only writes are the inventory
files on the controller.

## How it merges

- **Fill** (default): a value already in the record wins; discovery adds what is missing. Hand-written annotations the node cannot report (a
  disk's `role`, an interface's purpose, a storage `note`) always survive.
- **Overwrite** (`cluster_discover_overwrite: true`): the live value replaces the configured one; annotations still survive.
- Lists of disks, ZFS pools, guests, nodes, storages, pools, realms, SDN objects and directory mappings merge **element-wise on their identity**
  (`dev`, `name`, `id`, `zone`, ...), so a new disk is appended and an annotated disk keeps its annotation. Other lists are one value.
- A discovered `null` means "not observed" and never fills or overwrites anything.
- The merge and the drift report are the collection's `config_merge` / `config_drift` filters; the files are rendered by `to_config_yaml` in
  the exact style the repository's yamllint enforces, keys in their existing order, so diffs stay minimal.

## Where it writes

| `cluster_discover_write` | Node record | Cluster record |
| --- | --- | --- |
| `additional` (default) | `<inventory>/discovered/host_vars/<host>/node.yml` | `<inventory>/discovered/group_vars/<group>/cluster.yml` |
| `in_place` | `<inventory>/host_vars/<host>/node.yml` | `<inventory>/group_vars/<group>/cluster.yml` |

The `discovered/` tree mirrors the inventory layout but is never loaded (`ansible.cfg` ignores it), so the default run is a proposal: diff it,
then copy it in or re-run with `in_place`. The first in-place run re-renders a hand-formatted file into the generated style (comments other
than the banner are lost; git keeps the previous version, or set `cluster_discover_backup: true`). Every later run is `changed=0` until the
cluster changes.

`--check --diff` shows exactly what would be written without writing; `cluster_discover_strict: true` fails the run on any difference between
the configuration and the live cluster, which makes the play a drift gate.

- **Privilege:** runs as root on the PVE nodes (the admission gate asserts it); `pvesh` and the Ceph admin keyring need it.
- **Facts:** the play must gather the `min`, `hardware` and `network` subsets (`playbooks/cluster-discover.yml` does).
- **Collections:** `ansible.builtin`, plus `get_sybers.cluster.ceph_info` (needs `python3-rados` on the node; skipped when `ceph.conf` is absent).
- **Platforms:** Debian (bookworm, trixie). **Min ansible:** 2.19.

| Variable | Required | Default | Description |
| --- | --- | --- | --- |
| `cluster_discover_inventory_dir` | No | `{{ inventory_dir }}` | Inventory directory the records are read from and written to. |
| `cluster_discover_group` | No | `proxmox_cluster` | Group whose `group_vars/<group>/cluster.yml` holds the cluster snapshot. |
| `cluster_discover_write` | No | `additional` | `additional` (proposal files under `discovered/`) or `in_place`. |
| `cluster_discover_overwrite` | No | `false` | Live values replace configured ones (annotations kept). |
| `cluster_discover_backup` | No | `false` | Timestamped backup beside a file rewritten in place. |
| `cluster_discover_strict` | No | `false` | Fail when the configuration disagrees with the live cluster. |
| `cluster_discover_ceph` | No | `true` | Gather the Ceph side (auto-skipped without `ceph.conf`). |
| `cluster_discover_delegate_to` | No | `localhost` | The host holding the inventory checkout. |

The role publishes `cluster_discover_node_facts`, `cluster_discover_cluster_facts` and `cluster_discover_ceph_nodes` (the raw gathered
records) as facts; a caller can supply them itself and include `tasks_from: render` to merge and write without gathering, which is how the
`discover` molecule scenario proves the fill/overwrite/drift semantics against a committed fixture.

None. The admission gate (`cluster_preflight`) is included explicitly at the point of need.

```yaml
- name: "Discover the cluster and fill the inventory records from it"
  hosts: proxmox_cluster
  gather_facts: true
  gather_subset: ['!all', 'min', 'hardware', 'network']
  roles:
    - role: get_sybers.cluster.cluster_discover
```

Idempotent: a second run with the same mode rewrites nothing once the records match the cluster. Rollback is `git checkout` of the inventory
files (or the backup when enabled); the cluster itself is never touched.
