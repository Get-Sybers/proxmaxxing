# Reference

Technical information: the contracts, the formats, the rules.

| Reference | What it specifies |
| --- | --- |
| [Inventory](../../inventory/README.md) | The single config home: groups, the collection variables, desired state versus the discovered As-Is records, the placeholder contract of the template. |
| [`cluster_preflight`](../../roles/cluster_preflight/README.md) | The admission gate: root, a PVE cluster node, and (opt-in) a live admin Ludus API key in the environment. |
| [`cluster_discover`](../../roles/cluster_discover/README.md) | What is gathered, how it merges (fill, overwrite, keyed lists), where it writes, the drift gate. |
| [`cluster_ludus_install`](../../roles/cluster_ludus_install/README.md) | The Ludus server install and the SAFE `config.yml` keys it reconciles. |
| [`cluster_secrets`](../../roles/cluster_secrets/README.md) | The consume-a-secret interface over the house credential store. |
| [`cluster_pb_store`](../../roles/cluster_pb_store/README.md) | The PocketBase API mechanics: superuser auth, the credentials collection, the record primitives. |
| [`cluster_ludus_auth`](../../roles/cluster_ludus_auth/README.md) | The single-action task files that fetch, prove, persist and mint a Ludus API key. |
| [`cluster_ceph_orphan_sweep`](../../roles/cluster_ceph_orphan_sweep/README.md) | The three gates an RBD image passes before it is called an orphan. |
| [`cluster_patch_ludus`](../../roles/cluster_patch_ludus/README.md) | The patch manifest, its markers and its version guard. |
| [`cluster_patch_packer_iso`](../../roles/cluster_patch_packer_iso/README.md) | The sha256-keyed ISO manifest (`meta/iso-inventory.yml`) and the link step. |
| [`cluster_plugin_packer`](../../roles/cluster_plugin_packer/README.md) | The pinned packer plugin set and its checksum verification. |
| [`sysmon_linux`](../../roles/sysmon_linux/README.md) | The Sysmon for Linux install behind the audit-logging supply-chain gate. |
| [Plugins](../../README.md) | `ceph_info` (read-only Ceph facts over librados) and the `config_merge`, `config_drift`, `to_config_yaml` filters, documented in their `DOCUMENTATION` blocks (`ansible-doc -t filter get_sybers.cluster.config_merge`). |
| [Proxmox LDAP / Active Directory authentication](proxmox-ldap-authentication.md) | Reference notes on connecting Proxmox VE realms to a directory, syncing users and groups, and keeping a local escape hatch. |
| [Standards](../standards/02-Ansible-Standards.md) | The Ansible standard, the [CI workflow](../standards/03-ansible-ci-workflow.md) and the [linting and conformance gate](../standards/04-Linting-and-Conformance.md) this repository implements. |
