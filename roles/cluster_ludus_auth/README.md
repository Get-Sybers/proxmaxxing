One home for "hold a Ludus API key and prove it". Everything is Ludus's own
machinery, used as intended (rule 10):

- **fetch** — the key record comes from PocketBase (Ludus's own database)
  through its REST API. Preferred path: **Ludus's own `X-API-KEY` auth on the
  PB-native route** (`credential_fetch_apikey.yml`) — the caller's admin key,
  no superuser and no file read at all (a bogus key is rejected by the
  middleware, an unauthenticated read returns an empty list). Cold-start fallback: the PB superuser via `cluster_pb_store`, whose
  password is Ludus's ROOT key — the one credential no API can supply. Never
  `sqlite3` on `data.db`.
- **proof** — the Ludus v2 API `/whoami` HTTP status is the auth boundary.
  Never the CLI's exit code: the `ludus` CLI exits `rc=0` on an invalid key
  (`[ERROR] Invalid API key` on stderr only).
- **persistence** — the proven key is written as a sourceable
  `export LUDUS_API_KEY=…` line (`$HOME/.config/ludus/ludus.env`, 0600 root).
  That env var is Ludus's own documented headless mechanism (the CLI otherwise
  wants the system keyring, infeasible headless; an `apikey:` line in
  `config.yml` is parsed but never authenticates),
  and it is the same variable every env-only consumer here reads. `config.yml`
  gets the server URL only. Never argv (world-readable via `/proc`), `no_log`
  end to end.
- **mint** — the Ludus admin API (`/user/apikey?userID=…`), with a
  wrong-target guard (Ludus keys are userID-prefixed).
Disk touches: Ludus's own `/opt/ludus/config.yml` is READ for the
`database_encryption_key` that seals the PB record values (no API exposes it,
by design); the 0600 env file above is written; and rotation uses a transient
0400 staging file (a crash-safety copy for the window where the new key exists
only in memory — removed the moment the store round trip verifies).
This role is a **library of single-action task files**. It decides nothing about whether it applies; there is no default
sequence (a bare include fails loudly). The chains live in the
`get_sybers.cluster` playbooks:
| play | chain |
|---|---|
| `ludus-ra-auth.yml` | prove an identity's stored key end to end, write the sourceable export line |
| `ludus-key-rotate.yml` | mint a new key, home it in PocketBase, refresh the export line |
Those plays are the user-facing usage; the inputs are listed below and in
[`defaults/main.yml`](defaults/main.yml).
| var | default | meaning |
|---|---|---|
| `cluster_ludus_auth_identity` | `RA` | the Ludus userID being authenticated |
| `cluster_ludus_auth_record` | `<identity>.apikey` | the `gs_infra_credentials` record |
| `cluster_ludus_auth_api_url` | `https://127.0.0.1:8080/api/v2` | the local Ludus API |
| `cluster_ludus_auth_env_file` | `$HOME/.config/ludus/ludus.env` | where `env_file_write.yml` writes the proven key's export line |
| `cluster_ludus_auth_cli_config_file` | `$HOME/.config/ludus/config.yml` | where `cli_config_write.yml` writes the CLI's server URL (no key) |
| `cluster_ludus_auth_mint_target` | `RA` | userID whose key `key_mint.yml` mints |
| `cluster_ludus_auth_staging_file` | `/root/.ludus-key-rotate-staging` | rotation crash-safety copy |
Published non-secret facts: `cluster_ludus_auth_status`,
`cluster_ludus_auth_user`, `cluster_ludus_auth_is_admin`. Secret facts are
`_cla_*`, `no_log` throughout, and cleared by `forget.yml`.
`get_sybers.ludus_auth_check` (the shared env-only task-role the range
collections ship) is the **env-only check**: it resolves `LUDUS_API_KEY` from
the environment, holds no secret access, and is what range/infra plays use to
*assert a key arrived*. This role is the **cluster-tier holder**: it may fetch
(PB) and mint (admin API). Anything outside this collection receives keys by
injection and asserts with `ludus_auth_check`.
