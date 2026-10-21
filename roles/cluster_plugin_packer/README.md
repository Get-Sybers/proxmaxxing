Reproduces the packer plugin tree under `/opt/ludus/resources/packer/plugins` — the directory `ludus-server --update` never restores and its
own refresh path can wipe (it removes a plugin's directory before downloading the replacement, so a failed download leaves nothing). The role
installs the pinned plugin set idempotently with `packer plugins install`, re-verifies each on-disk binary against its recorded SHA256SUM,
asserts the stock `ludus:users` ownership back onto the tree, and never deletes anything — so template builds stop dying with
"Unknown source type proxmox-iso".

- **Privilege:** runs as **root** on the Ludus host (install runs as root, then the role asserts the stock `ludus:users` ownership back).
- **Tooling:** `packer` must be on `PATH`; the plugin root's parent (`/opt/ludus/resources/packer`) must already exist.
- **Collections:** `ansible.builtin` only.
- **Platforms:** Debian (bookworm, trixie). **Min ansible:** 2.19.
| Variable | Required | Default | Description |
|---|---|---|---|
| `cluster_plugin_packer_root` | No | `/opt/ludus/resources/packer/plugins` | The plugin root packer resolves from (`PACKER_PLUGIN_PATH`). |
| `cluster_plugin_packer_owner` | No | `ludus` | Owner asserted back onto the plugin tree after install. |
| `cluster_plugin_packer_group` | No | `users` | Group asserted back onto the plugin tree (the `ludus` user's primary group). |
| `cluster_plugin_packer_list` | No | `[proxmox 1.2.4, ansible 1.1.1]` | The pinned set — a list of `{source, version}`; each binary is re-verified against its SHA256SUM. |
None. The role drives the packer CLI against an existing Ludus install and has no infrastructure prerequisite of its own.

```yaml
- name: Ensure the pinned packer plugins exist under the Ludus plugin root
  hosts: ludus_server
  become: true
  roles:
    - get_sybers.cluster.cluster_plugin_packer
```

Idempotent. A plugin that is already present with a matching recorded checksum is `ok`, not `changed` — the install task does not run for it.
Ownership is converged on every run, nothing is ever deleted, and verification trusts `packer plugins installed` plus a disk re-scan (which
also asserts no pre-existing file went missing), never a task's own exit code. Re-running a converged host is `changed=0`.
