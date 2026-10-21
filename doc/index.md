# `get_sybers.cluster`

`get_sybers.cluster` is the cluster tier of the Get-Sybers lab: an Ansible collection that operates the Proxmox VE nodes themselves —
Ceph mesh, tuning and diagnosis, SDN zone and VNets, storage links, apt repositories and rolling upgrades, audit logging — and the
Ludus server that runs on the master node, with its credential store (an encrypted ZFS vault mirrored into PocketBase), its API
identities and keys, its local patches and its packer plugins.

The plays run at host-root level on the nodes (the cluster plays, over SSH) or on the master node itself (the credential, vault and
Ludus plays, `hosts: localhost`). Every site-specific value lives in `inventory/`, which the repository ships only as the template
`inventory/example/`; `make config` copies it into place and `playbooks/cluster-discover.yml` fills the As-Is records from the live
cluster. Released versions are published to Ansible Galaxy by the Release workflow; the collection also installs straight from this
repository as a git source (the `galaxy.yml` manifest is at the repository root).

---

## In this documentation

| | |
| --- | --- |
| [How-to guides](howto/index.md) | **Step-by-step guides** covering the operations: configure a cluster, discover it, bring up the storage mesh and Ceph, run the credential store, run the plays from the controller container |
| [Reference](reference/index.md) | **Technical information**: the inventory contract, the roles, the plugins, the Proxmox LDAP/AD authentication notes |
| [Standards](standards/02-Ansible-Standards.md) | **The house rules** every role, play and repository control is held to: the Ansible standard, the [CI workflow](standards/03-ansible-ci-workflow.md), [linting, conformance and the merge gate](standards/04-Linting-and-Conformance.md) |

The roles document their own contracts: [`cluster_preflight`](../roles/cluster_preflight/README.md),
[`cluster_discover`](../roles/cluster_discover/README.md), [`cluster_ludus_install`](../roles/cluster_ludus_install/README.md),
[`cluster_secrets`](../roles/cluster_secrets/README.md), [`cluster_pb_store`](../roles/cluster_pb_store/README.md),
[`cluster_ludus_auth`](../roles/cluster_ludus_auth/README.md), [`cluster_ceph_orphan_sweep`](../roles/cluster_ceph_orphan_sweep/README.md),
[`cluster_patch_ludus`](../roles/cluster_patch_ludus/README.md), [`cluster_patch_packer_iso`](../roles/cluster_patch_packer_iso/README.md),
[`cluster_plugin_packer`](../roles/cluster_plugin_packer/README.md), [`sysmon_linux`](../roles/sysmon_linux/README.md).
The inventory documents the configuration contract: [`inventory/`](../inventory/README.md).

---

## Project and community

`get_sybers.cluster` is free software under the [GNU Affero General Public License v3.0](../LICENSE). It is part of the Get-Sybers lab,
alongside the hardened LXC tier in [get-sybers/lxc](https://github.com/get-sybers/lxc) (`get_sybers.lxc`), which builds every container
that runs on the cluster this tier operates.

- [Contribute to the project](../CONTRIBUTING.md)
- [Report a vulnerability](../SECURITY.md)
- [Code of conduct](../CODE_OF_CONDUCT.md)
- [Maintainers](../MAINTAINERS)
