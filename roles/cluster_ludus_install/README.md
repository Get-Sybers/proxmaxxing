Stands up and then idempotently reconciles a Ludus server on a Proxmox cluster node. On a host that already has Ludus it is purely a converger:
it reads `/opt/ludus/config.yml`, enforces the SAFE keys this cluster needs (shared Ceph storage with the `raw` format, cluster mode, the SDN
zone, the reserved range number), stages the ROOT API key into the house credential store, and verifies the services and the on-disk result —
a second run is `changed=0`. On a host with no install it refuses by default; with `cluster_ludus_install_run_installer=true` it downloads the
official `ludus-server` binary and runs it non-interactively (on an *existing* Proxmox host Ludus installs without a reboot), then reconciles.

It never rewrites `database_encryption_key` (that key decrypts every stored credential; the config step captures it before any edit and asserts it
unchanged after), and it leaves the host network keys alone unless `cluster_ludus_install_manage_network` is set — the working Ceph-mesh network is
not restyled by a guess (run-sheet caution C1).

- **Privilege:** runs as **root** on the Ludus/Proxmox node — it writes under `/opt/ludus`, stages a key under `/root`, and restarts systemd units.
- **Collections:** `ansible.builtin` only.
- **State:** either a staged Ludus install (`/opt/ludus/config.yml` + `/opt/ludus/install/root-api-key`), or `run_installer=true` with a binary URL.
- **Platforms:** Debian (bookworm, trixie). **Min ansible:** 2.19.

| Variable | Required | Default | Description |
| --- | --- | --- | --- |
| `cluster_ludus_install_root` | No | `/opt/ludus` | Install root (where `config.yml` and `install/root-api-key` live). |
| `cluster_ludus_install_run_installer` | No | `false` | When true *and* no install is found, download and run `ludus-server --no-prompt`. |
| `cluster_ludus_install_binary_url` | No | `""` | URL of the `ludus-server` binary (required when installing). |
| `cluster_ludus_install_binary_checksum` | No | `""` | Optional `algo:hex` checksum for the download. |
| `cluster_ludus_install_version` | No | `""` | When set, assert `ludus version` reports it. |
| `cluster_ludus_install_vm_storage_pool` | No | `{{ ceph_pool }}` | `proxmox_vm_storage_pool` to enforce (the inventory's shared guest pool). |
| `cluster_ludus_install_vm_storage_format` | No | `raw` | `proxmox_vm_storage_format` to enforce (Ceph RBD/ZFS need `raw`). |
| `cluster_ludus_install_iso_storage_pool` | No | `local` | `proxmox_iso_storage_pool` to enforce (RBD cannot hold ISOs). |
| `cluster_ludus_install_reserved_range_numbers` | No | `{{ ludus_reserved_range_numbers }}` | `reserved_range_numbers` to enforce (keeps ranges off the cluster's own `10.N.0.0/16` nets). |
| `cluster_ludus_install_cluster_mode` | No | `true` | `cluster_mode` to enforce. |
| `cluster_ludus_install_sdn_zone` | No | `{{ sdn_zone }}` | `sdn_zone` to enforce (the inventory's VXLAN zone). |
| `cluster_ludus_install_vxlan_tag_base` | No | `0` | `vxlan_tag_base` to enforce. |
| `cluster_ludus_install_proxmox_node` | No | `{{ inventory_hostname }}` | `proxmox_node` to enforce. |
| `cluster_ludus_install_manage_network` | No | `false` | Also reconcile the host network keys below. |
| `cluster_ludus_install_net_interface` | No | `""` | `proxmox_interface` (only when `manage_network`). |
| `cluster_ludus_install_net_local_ip` | No | `""` | `proxmox_local_ip` (only when `manage_network`). |
| `cluster_ludus_install_net_gateway` | No | `""` | `proxmox_gateway` (only when `manage_network`). |
| `cluster_ludus_install_net_netmask` | No | `""` | `proxmox_netmask` (only when `manage_network`). |
| `cluster_ludus_install_stage_root_key` | No | `true` | Stage `install/root-api-key` into the house credential store. |
| `cluster_ludus_install_vault_dir` | No | `/root/ludus-credentials` | Credential-store dir the ROOT key is staged into (as `ROOT.apikey`). |
| `cluster_ludus_install_verify_whoami` | No | `false` | Prove an exported `LUDUS_API_KEY` authenticates at `/whoami`. |
| `cluster_ludus_install_api_url` | No | `https://127.0.0.1:8080/api/v2` | User API base URL for the `/whoami` check. |
| `cluster_ludus_install_validate_certs` | No | `false` | Validate the self-signed TLS cert for the `/whoami` check. |

The exact `config.yml` keys this role manages (and the scalar each is written as) live in `vars/main.yml` as role-internal data, not as inputs —
`database_encryption_key`, the ports, the licence key and `data_directory` are deliberately absent so the installer's values are never touched.

**Requirements:** none (empty `dependencies`). The VXLAN SDN zone and the per-range VNets/ACLs are a separate concern — ensure the zone with
`playbooks/cluster-sdn-zone.yml`, then the VNets and ACLs with `playbooks/cluster-sdn-setup.yml`.

```yaml
- name: Install and reconcile the Ludus server
  hosts: proxmox_master
  roles:
    - get_sybers.cluster.cluster_preflight
    - get_sybers.cluster.cluster_ludus_install
```

Fully idempotent. `config.yml` keys are reconciled with `lineinfile` (every other line, including the DEK, is preserved); a changed key notifies a
single `ludus`/`ludus-admin` restart, flushed before verification; the ROOT key is staged by content hash, so a second run is `changed=0`. The play
that calls this role should refuse `--check` — the installer and the service restart cannot be simulated.
