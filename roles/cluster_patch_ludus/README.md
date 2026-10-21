After a `ludus-server --update` re-extracts the stock Ludus tree over `/opt/ludus` and reverts every local change, this role puts the local
patches back. Each patch is an exact-string substitution declared in `vars/main.yml`, idempotent via a marker and proven by re-reading the file
from disk, so range deploys keep the local fixes (ERR-13/21/22/103, ACL-STORAGE, GRUB-ZFS, SDN-SOURCE/PRECHECK, ADGUARD) instead of silently
running stock. A version guard refuses to apply a manifest derived from a different Ludus version before any file is touched.

- **Privilege:** runs as **root** on the Proxmox/Ludus host — it rewrites files under `/opt/ludus` and enforces their `ludus:ludus 0644`
  extraction ownership (root-owned or 0600 breaks every `ludus range deploy` with EACCES for the non-root `ludus` service user).
- **Collections:** `ansible.builtin` only. (The `ansible.windows.*` strings in `vars/main.yml` are patch *payloads* written into Ludus's own
  files, not modules this role executes.)
- **State:** a fully-staged Ludus install (`/opt/ludus/install/.stage-{1,2,3}-complete`) with the stock target files present.
- **Platforms:** Debian (bookworm, trixie). **Min ansible:** 2.19.
| Variable | Required | Default | Description |
|---|---|---|---|
| `cluster_patch_ludus_root` | No | `/opt/ludus` | Ludus install root; the manifest stores paths relative to this. |
| `cluster_patch_ludus_derived_from` | No | `2.3.1` | Ludus version the manifest was derived from; the guard asserts the running binary matches. |
| `cluster_patch_ludus_skip_version_check` | No | `false` | Skip the version guard — only after confirming every stock payload still resolves. |
| `cluster_patch_ludus_file_owner` | No | `ludus` | Owner each patched file is written back with (the extraction value). |
| `cluster_patch_ludus_file_group` | No | `ludus` | Group each patched file is written back with. |
| `cluster_patch_ludus_file_mode` | No | `"0644"` | Mode each patched file is written back with. |
The patch manifest itself (`cluster_patch_ludus_list`, `cluster_patch_ludus_reorder`) lives in `vars/main.yml` as role-internal data, not as inputs.
None. Empty by design — the role only rewrites files that already exist in the stock tree and has no infrastructure prerequisite.

```yaml
- name: Reconcile local Ludus patches after an update
  hosts: ludus_server
  become: true
  roles:
    - get_sybers.cluster.cluster_patch_ludus
```

Fully idempotent. A patch whose marker is already present is a no-op, so a second run is `changed=0`; ownership is converged on every run
(not merely written), and every patched file is re-read and re-parsed as YAML before the role reports success. Under `--check` the pre-flight
still reads the tree as-is while the write and post-verify steps are skipped, so a check run previews without false failures.
