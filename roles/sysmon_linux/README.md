Installs, configures, and enables Sysmon for Linux (`sysmonforlinux` + `sysinternalsebpf`) on a Proxmox cluster node via a push-model
supply-chain gate. The caller stages digest-gated `.debs` on the controller; this role pushes them to the node, re-verifies each sha256 **on
the node** (proving the artefact survived transport unchanged), installs `sysinternalsebpf` then `sysmonforlinux` via apt, renders and deploys
the Sysmon config, and ensures the `sysmon` service is enabled and running — so no node needs a route to Nexus or packages.microsoft.com.

- **Privilege:** runs as **root** on the cluster node — it `apt`-installs packages, runs `sysmon -accepteula -i`, and manages the systemd unit.
- **Caller prerequisite:** the digest-gated `.debs` must already be staged on the controller at `sysmon_linux_stage_dir` (Play 1 of
  `cluster-audit-logging.yml` does this); `sysmon_linux_artefacts` must list them in dependency order (`sysinternalsebpf` before `sysmonforlinux`).
- **Collections:** `ansible.builtin` only.
- **Platforms:** Debian (trixie). **Min ansible:** 2.19.
| Variable | Required | Default | Description |
|---|---|---|---|
| `sysmon_linux_artefacts` | No | `[]` | Artefact list `[{name, version, sha256, deb}]` in install order. Caller MUST supply it; empty fails loudly. |
| `sysmon_linux_stage_dir` | No | `/var/cache/sysmon-linux` | On-controller staging dir the caller wrote the `.debs` to. |
| `sysmon_linux_node_stage_dir` | No | `/var/cache/sysmon-linux` | On-node staging dir the artefacts are pushed to. |
| `sysmon_linux_config_path` | No | `/etc/sysmon/config.xml` | Config file path on each cluster node. |
| `sysmon_linux_schema_version` | No | `"4.90"` | Sysmon schema version; must match the `sysmonforlinux` build being installed. |
| `sysmon_linux_hash_algorithms` | No | `sha256` | Hash algorithm(s) recorded in each event. |
| `sysmon_linux_excluded_dest_prefixes` | No | 6 prefixes (see defaults) | NetworkConnect destination prefixes excluded from events (intra-cluster noise). |
| `sysmon_linux_watched_paths` | No | 6 paths (see defaults) | FileCreate/FileDelete paths that fire events (integrity-relevant only). |
None. The caller stages the artefacts before including this role; it has no `meta` dependency.

```yaml
- name: Install and enable Sysmon for Linux on the cluster nodes
  hosts: proxmox_cluster
  become: true
  tasks:
    - name: Install, configure, and enable Sysmon
      ansible.builtin.include_role:
        name: get_sybers.cluster.sysmon_linux
      vars:
        sysmon_linux_artefacts:
          - { name: sysinternalsebpf, version: "1.5.0", sha256: "<digest>", deb: sysinternalsebpf.deb }
          - { name: sysmonforlinux, version: "1.3.5", sha256: "<digest>", deb: sysmonforlinux.deb }
```

Idempotent. Package installs are guarded on `package_facts`, so an already-installed pinned version is skipped; the config is a template that
reports `changed` only when its rendered content differs; first-time `sysmon -i` versus a config-changed `sysmon -c` is chosen on
`service_facts`; and the service enable/start is declarative. A converged node re-runs `changed=0`.
