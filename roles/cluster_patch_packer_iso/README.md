Stops packer template builds from re-downloading ISOs the build node already holds. The role reads a sha256-keyed ISO manifest, derives the
build node from `config.yml` (never a hardcoded node name), and hardlinks each held image under the URL-derived basename Proxmox looks for
(so the native `iso_download_pve` path finds the file instead of fetching it again). A template
whose ISO we do not hold is left downloading, never turned into a broken reference.

- **Privilege:** runs as **root** on the Proxmox **build node** — it reads `/opt/ludus/config.yml`, scans the packer template trees, and links
  into `/var/lib/vz/template/iso`.
- **Collections:** `ansible.builtin` only, plus the shipped helper script `link-registered-isos.py` (run via `ansible.builtin.script`).
- **State:** the ISO manifest must exist (ships as the collection's `meta/iso-inventory.yml`); without it the role refuses rather than guess.
- **Platforms:** Debian (Proxmox VE node). **Min ansible:** 2.19.
| Variable | Required | Default | Description |
|---|---|---|---|
| `cluster_patch_packer_iso_manifest` | No | `{{ role_path }}/../../meta/iso-inventory.yml` | Path to the sha256 ISO inventory; the role never guesses an ISO. |
| `cluster_patch_packer_iso_search_paths` | No | `[/opt/ludus/packer, /opt/ludus/users]` | Both template trees that get clobbered (by `--update` and `source add --force`). |
| `cluster_patch_packer_iso_storage_pool` | No | `local` | The Proxmox storage the ISOs live on (matches Ludus's `iso_storage_pool`). |
| `cluster_patch_packer_iso_apply` | No | `false` | Report only by default; set true to act (the template-rewrite path is superseded and refuses to write). |
| `cluster_patch_packer_iso_config_path` | No | `/opt/ludus/config.yml` | Ludus config read at run time to derive the build node. |
| `cluster_patch_packer_iso_iso_dir` | No | `/var/lib/vz/template/iso` | Where `local` keeps ISOs; the linker makes held images discoverable here. |
None. The role drives an existing Ludus/Proxmox install and has no infrastructure prerequisite of its own.

```yaml
- name: Make held ISOs discoverable to packer (report, then apply the links)
  hosts: ludus_build_node
  become: true
  tasks:
    - name: Report what is holdable
      ansible.builtin.include_role:
        name: get_sybers.cluster.cluster_patch_packer_iso
    - name: Link held ISOs under the expected name
      ansible.builtin.include_role:
        name: get_sybers.cluster.cluster_patch_packer_iso
      vars:
        cluster_patch_packer_iso_apply: true
```

Idempotent. A template already carrying the `LOCAL PATCH (ISO-REDIRECT)` marker is classified `already`; the hardlink step is keyed on sha256
and skips images already linked under the expected name. In the default report-only mode nothing on disk changes at all. The legacy
template-rewrite path is deliberately disabled and asserts rather than writing, so `cluster_patch_packer_iso_apply` only ever creates missing hardlinks.
