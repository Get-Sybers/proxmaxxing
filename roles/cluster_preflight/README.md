The admission gate cluster plays include **first**. It proves three things before any cluster work runs: the play is executing as root, the
host is a Proxmox VE cluster node (`/etc/pve` present, and the host appears in `pvecm nodes` or the `cluster_preflight_cluster_group` inventory group), and —
only when the calling play opts in via `cluster_preflight_require_api_admin` — that a `LUDUS_API_KEY` in the **environment** authenticates to
the Ludus API as an admin. The API check is env-only by design: this role never stats, slurps, or looks up a key file; key delivery is the
calling play's job.

- **Privilege:** runs as **root** — the first check asserts effective uid 0.
- **Host:** a Proxmox VE node of the cluster.
- **Collections:** `ansible.builtin` only (`uri` for the optional `/whoami` check).
- **API check (opt-in):** the calling play must export `LUDUS_API_KEY` first (e.g. via `playbooks/ludus-ra-auth.yml`).
- **Platforms:** Debian (bookworm, trixie). **Min ansible:** 2.19.
| Variable | Required | Default | Description |
|---|---|---|---|
| `cluster_preflight_require_api_admin` | No | `false` | Set true by the PLAY (at include time) to run the env API-admin check. |
| `cluster_preflight_api_url` | No | `https://127.0.0.1:8080/api/v2` | The Ludus API as seen from the host the play runs on. |
| `cluster_preflight_delegate_to` | No | `{{ inventory_hostname }}` | The host every check executes on; a caller that delegates its own work must pass the same value. |
| `cluster_preflight_cluster_group` | No | `proxmox_cluster` | Inventory group of the cluster nodes; membership admits a host `pvecm nodes` does not yet list. |
The `cluster_preflight_auth_*` facts (status, user, admin) are published by the API check as internal results, not inputs.
None. Composition is explicit at the point of need — the role never includes `cluster_secrets` and has no `meta` dependency.

```yaml
- name: A cluster play that calls the Ludus API
  hosts: ludus_server
  become: true
  tasks:
    - name: Admission gate — root, PVE node, and a live admin API key
      ansible.builtin.include_role:
        name: get_sybers.cluster.cluster_preflight
      vars:
        cluster_preflight_require_api_admin: true
```

Read-only. Every step is an assertion or a fact-find — `stat`, `command` with `changed_when: false`, and a `uri` fact-find against `/whoami` —
so the role changes nothing, is `changed=0` on every run, and is safe under `--check` (the checks run so a dry run still gates meaningfully).
