THE consume-a-secret abstraction for the collection. A service role fetches a secret through one interface — `tasks_from: get.yml` with an
`cluster_secrets_request` — and receives it back as the registered, `no_log` fact `cluster_secrets_result` (`{ value, present }`). Because the mechanism is
behind this one interface, the whole estate can migrate from the file backend to a keychain by swapping `cluster_secrets_backend`, not by editing
every service. Two convenience entry points, `ludus_root_key` and `ludus_user_key`, resolve the Ludus ROOT (bootstrap) and operational API keys
without any caller open-coding a credential path.

- **Privilege:** runs as **root** on the node — the house credential store (`/root/ludus-credentials`) is root-only and ZFS-native-encrypted,
  and the ROOT key's install-path fallback is likewise root-readable.
- **Collections:** `ansible.builtin` only.
- **State:** for the file backend, the requested path must exist (a locked vault leaves an empty directory, which reads as absent).
- **Platforms:** Debian (bookworm, trixie). **Min ansible:** 2.19.
| Variable | Required | Default | Description |
|---|---|---|---|
| `cluster_secrets_backend` | No | `file` | Secret backend: `file` reads a host path; `keychain` delegates to the OS keychain (reserved). |
| `cluster_secrets_request` | No | `{}` | Secret request dict (at minimum `name`; file backend adds `path`, optional `regex`, `required`). |
| `cluster_secrets_vault_dir` | No | `/root/ludus-credentials` | Root of the credential store used by the convenience entry points. |
| `cluster_secrets_root_vault_path` | No | `{{ cluster_secrets_vault_dir }}/ROOT.apikey` | Path to the ROOT API key in the vault (computed). |
| `cluster_secrets_root_install_path` | No | `/opt/ludus/install/root-api-key` | Fallback path where Ludus installs the ROOT key at bootstrap. |
| `cluster_secrets_root_regex` | No | `ROOT\.[^\s]+` | Regex extracting the ROOT token from a possibly-labelled file. |
| `cluster_secrets_ludus_user_id` | No | `RA` | Operational Ludus user ID (used by the `ludus_user_key` entry point). |
None. This is the leaf credential role other roles depend on (e.g. `cluster_pb_store` claims the ROOT key through it); it includes nothing
itself.

```yaml
- name: Fetch a secret through the house interface
  hosts: ludus_server
  become: true
  tasks:
    - name: Resolve the operational Ludus API key
      ansible.builtin.include_role:
        name: get_sybers.cluster.cluster_secrets
        tasks_from: ludus_user_key
    - name: Fetch an arbitrary secret from the file backend
      ansible.builtin.include_role:
        name: get_sybers.cluster.cluster_secrets
        tasks_from: get
      vars:
        cluster_secrets_request:
          name: ra-api-key
          path: /root/ludus-credentials/RA.apikey
          regex: 'RA\.[A-Za-z0-9._+/=-]+'
```

Read-only. The role reads a path (or the keychain) and returns the secret as a fact; it `stat`s, `slurp`s, and `set_fact`s but changes nothing
on disk, so it is `changed=0` on every run and safe under `--check`. All secret-carrying tasks are `no_log`, and `forget.yml` overwrites the
facts it set.
