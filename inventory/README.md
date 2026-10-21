# inventory/ — the single config home

Everything site-specific the `get_sybers.cluster` plays and roles consume lives in this directory and nowhere else: no play carries a
`vars:` block, no role default names a host, a pool, a zone or an address. `ansible.cfg` points here, so a play needs no `-i`.

The repository keeps only the **template** of that configuration, `inventory/example/`. The real files are created from it by
`make config` and are untracked (`.gitignore`), so a node name, a subnet, a pool or a serial never enters version control:

```text
inventory/
├── README.md
├── example/                       # the template — the only configuration the repository carries
│   ├── hosts.yml                  #   the controlled host set and group membership — nothing else
│   ├── group_vars/
│   │   ├── all/                   #   values every play reads, node-side and controller-side (localhost is a declared host)
│   │   │   ├── cluster.yml        #     master node, cluster_slug, management LAN
│   │   │   ├── ludus.yml          #     Ludus control plane: paths, API, identities, reserved range numbers
│   │   │   ├── credentials.yml    #     the ZFS vault + PocketBase credential store (per-play pointers to one value)
│   │   │   ├── proxmox_api.yml    #     admin PVE API credential (read from PROXMOX_* env vars, never stored)
│   │   │   ├── audit_artefacts.yml #    supply-chain pins and mirrors for audit logging
│   │   │   └── ghost9.yml, identity.yml, sources.yml
│   │   └── proxmox_cluster/       #   desired state of the cluster nodes, one file per topic
│   │       ├── ansible.yml        #     connection variables only (ansible_host from the node record, ansible_user)
│   │       ├── cluster.yml        #     As-Is skeleton — FILLED BY playbooks/cluster-discover.yml
│   │       └── ceph.yml, mesh.yml, sdn.yml, storage_net.yml, node_repos.yml, node_upgrade.yml, audit_logging.yml
│   └── host_vars/pi-01, pi-02, pi-03/   # per-node values, one file per topic
│       ├── node.yml               #     As-Is skeleton — FILLED BY playbooks/cluster-discover.yml
│       ├── storage_net.yml        #     desired fast-storage links
│       └── sdn.yml                #     (master only) the NAT uplink
├── hosts.yml                      # untracked — your copy
├── group_vars/, host_vars/        # untracked — your copies
├── discovered/                    # untracked — proposal files cluster-discover.yml writes by default; never loaded
└── secrets/                       # vaulted -e files (see secrets/README.md); never loaded as inventory
```

## First run

```sh
make config                        # copies example/ into place without overwriting what is already there
$EDITOR inventory/hosts.yml inventory/group_vars/all/*.yml inventory/group_vars/proxmox_cluster/*.yml inventory/host_vars/*/*.yml
```

The template's contract:

- **Nodes** are `pi-01` (the master), `pi-02` and `pi-03`. Rename them in `hosts.yml` and rename the `host_vars/<host>/` directories to
  match; add or remove nodes the same way.
- **Addresses** are RFC 5737 documentation addresses: `192.0.2.0/24` stands for the management LAN (`cluster_lan_cidr`, each node's
  `mgmt_ip`), `198.51.100.0/24` for the Ceph mesh (`mesh_prefix`, the loopbacks) and `203.0.113.0/24` for the point-to-point storage
  links (`storage_links`). Replace them with yours.
- **`CHANGE-ME`** marks a value with no sensible example that every run needs: the guest RBD pool (`ceph_pool`), the master's NAT uplink
  (`sdn_nat_interface`), the ghost9 range CT id (`g9_vmid`), the break-glass GitHub repository and secret name the vault passphrase is
  copied to (`cv_gh_repo`, `cv_gh_secret_name`), and your own Ludus sources (`default_sources`). `grep -rn CHANGE-ME inventory/` finds
  what is left.
- **`cluster_slug`** names the files and directories the plays write on the nodes (the audit ruleset, the audit state and staging
  directories); the example is `get-sybers`.

`ansible.cfg` ignores `example/`, `discovered/` and `secrets/` as inventory sources, so the template is never loaded by mistake.

## Groups

| Group | Members | Meaning |
| --- | --- | --- |
| `proxmox_cluster` | every PVE node | the cluster plays target it |
| `proxmox_master` | the node that hosts the Ludus server | once-per-cluster steps run here; membership *is* the "master" role |
| `controller` | `localhost` | the credential, vault and token plays; declared so they receive `group_vars/all` |

## As-Is versus desired state

Two files are **discovered state**, written by [`playbooks/cluster-discover.yml`](../playbooks/cluster-discover.yml): `host_vars/<host>/node.yml`
(hardware, disks, pools, interfaces, guests, corosync and Ceph membership) and `group_vars/proxmox_cluster/cluster.yml` (cluster, storage,
access, pools, SDN, Ceph). The template ships them as skeletons that keep the key structure and the one value the plays need before the
first discovery run, each node's `mgmt_ip` (`ansible_host` is read from it). The plays read them for orientation and cross-checks, never
as a target to converge on. Every other file is **desired state**, written by hand.

Fill in or refresh the discovered records from the live cluster:

```sh
ansible-playbook playbooks/cluster-discover.yml                                   # proposals under discovered/ — diff, then adopt
ansible-playbook playbooks/cluster-discover.yml --check --diff                    # what would change, nothing written
ansible-playbook playbooks/cluster-discover.yml -e cluster_discover_write=in_place   # rewrite node.yml / cluster.yml here
ansible-playbook playbooks/cluster-discover.yml -e cluster_discover_write=in_place -e cluster_discover_overwrite=true
ansible-playbook playbooks/cluster-discover.yml -e cluster_discover_strict=true   # fail on any difference (drift gate)
```

A fill run (the default) keeps every value already in a record and adds what the node reports; an overwrite run replaces the discovered
values. Annotations the node cannot report — a disk's `role`, an interface's purpose — survive both, because disks, pools, guests and the
cluster's objects are merged on their identity (`dev`, `name`, `id`, ...), not by position. The role README
([`roles/cluster_discover`](../roles/cluster_discover/README.md)) lists every key.

## Adding a node

1. Add it to `proxmox_cluster` in `hosts.yml` (and to `proxmox_master` if it is the new master).
2. Write its desired state: `host_vars/<host>/storage_net.yml` and its entry in `group_vars/proxmox_cluster/mesh.yml`.
3. Create `host_vars/<host>/node.yml` from one of the template skeletons with its `mgmt_ip`, then run `cluster-discover.yml` to fill it.
