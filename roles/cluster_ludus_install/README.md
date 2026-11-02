Stands up and then idempotently reconciles a Ludus server on a Proxmox cluster node. On a host that already has Ludus it is purely a converger:
it reads `/opt/ludus/config.yml` and reconciles it from the single `ludus_config` map (the master's `host_vars/<master>/ludus_config.yml`, assembled
by reference from the `ludus_cfg_*` group vars and the cluster's `ceph_pool` / `sdn_zone` / `cluster_master_node` / `ludus_reserved_range_numbers`),
stages the ROOT API key into the house credential store, and verifies the services and the on-disk result — a second run is `changed=0`. On a host
with no install it refuses by default; with `cluster_ludus_install_run_installer=true` it downloads the official `ludus-server` binary and runs it
non-interactively (on an *existing* Proxmox host Ludus installs without a reboot), then reconciles.

Every key in the map whose resolved value is non-empty is written to `config.yml` (booleans lowercased, lists/dicts as JSON; an empty or null value is
skipped so the installer's own value is kept). Two sets are special:

- **Secret keys** (`cluster_ludus_install_secret_keys`, default `[database_encryption_key]`) are never rewritten — the config step reads the live file,
  asserts each configured secret already matches it (so a wrong vaulted value refuses the run rather than bricking the credential store), and leaves it
  untouched. It also captures `database_encryption_key` before any edit and asserts it unchanged after.
- **Host network keys** (`cluster_ludus_install_network_keys`) are reconciled only when `cluster_ludus_install_manage_network` is set — the working
  Ceph-mesh network is not restyled by a guess (run-sheet caution C1). Fill them from the live host with `playbooks/ludus-config-discover.yml`.

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
| `cluster_ludus_install_config` | No | `{{ ludus_config \| default(cluster_ludus_install_config_fallback) }}` | The `config.yml` keys to reconcile, as one map — the master's `ludus_config` host var is the source of truth. |
| `cluster_ludus_install_config_fallback` | No | *(safe cluster-mode skeleton)* | Used when no `ludus_config` is defined; its site values reference `cluster_master_node`, `ceph_pool`, `sdn_zone`, `sdn_vxlan_tag_base` and `ludus_reserved_range_numbers` (each guarded). |
| `cluster_ludus_install_secret_keys` | No | `[database_encryption_key]` | Keys verified against the live config and NEVER rewritten. |
| `cluster_ludus_install_manage_network` | No | `false` | Also reconcile the host network keys below. |
| `cluster_ludus_install_network_keys` | No | `[proxmox_interface, proxmox_local_ip, proxmox_public_ip, proxmox_gateway, proxmox_netmask]` | The host network keys, written only when `manage_network`. Filled by `playbooks/ludus-config-discover.yml`. |
| `cluster_ludus_install_stage_root_key` | No | `true` | Stage `install/root-api-key` into the house credential store. |
| `cluster_ludus_install_vault_dir` | No | `/root/ludus-credentials` | Credential-store dir the ROOT key is staged into (as `ROOT.apikey`). |
| `cluster_ludus_install_verify_whoami` | No | `false` | Prove an exported `LUDUS_API_KEY` authenticates at `/whoami`. |
| `cluster_ludus_install_api_url` | No | `https://127.0.0.1:8080/api/v2` | User API base URL for the `/whoami` check. |
| `cluster_ludus_install_validate_certs` | No | `false` | Validate the self-signed TLS cert for the `/whoami` check. |

The secret `database_encryption_key` is split out to the ansible-vault file `inventory/secrets/ludus.yml`
(`vault_ludus_database_encryption_key`, see its `.example`); pass it with `-e @inventory/secrets/ludus.yml --ask-vault-pass`. The ports, the licence
key and `data_directory` are ordinary keys of the map now — set them in the `ludus_cfg_*` group vars.

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
