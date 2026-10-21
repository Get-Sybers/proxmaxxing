The single home for PocketBase API mechanics, talking only to the PB-native `/api/collections/*` surface Ludus itself ships. Its `main` entry
point ensures the `gs_infra_credentials` collection exists with the ruled API rules (admins read; create/update/delete are superuser-only) —
creating it when absent, reconciling drifted rules when present, then re-probing and verifying the end state. Its record primitives
(`record_write`, `record_read`, `record_read_id`, `record_update`, `record_patch_fields`, `record_list`, `record_delete`) give `no_log` CRUD
over records and work against any collection when `cluster_pb_store_collection_name` is overridden at the include site.

- **Privilege:** runs as **root** on the Ludus/PVE node — the PB superuser password is the ROOT API key, claimed through `cluster_secrets`,
  which reads the root-only credential store.
- **Collections:** `ansible.builtin` modules; depends on the sibling role `get_sybers.cluster.cluster_secrets` for the ROOT key.
- **Service:** reaches the local Ludus/PocketBase server over HTTPS (self-signed cert; `cluster_pb_store_validate_certs` is false by default).
- **Platforms:** Debian (bookworm, trixie). **Min ansible:** 2.19.
| Variable | Required | Default | Description |
|---|---|---|---|
| `cluster_pb_store_base_url` | No | `https://127.0.0.1:8080` | The Ludus/PocketBase server as seen from the node the play runs on. |
| `cluster_pb_store_validate_certs` | No | `false` | Whether to validate the self-signed service TLS certificate. |
| `cluster_pb_store_superuser_identity` | No | `root@ludus.internal` | PB superuser identity Ludus creates with the ROOT key as password. |
| `cluster_pb_store_collection_name` | No | `gs_infra_credentials` | The collection ensured/operated on; override for the collection-agnostic primitives. |
| `cluster_pb_store_collection_rules` | No | admins read, writes `null` | API rules enforced: `list`/`view` require `isAdmin`; create/update/delete are superuser-only. |
| `cluster_pb_store_record_name` | No | `""` | Record name for `record_write`/`record_read`/`record_delete`. |
| `cluster_pb_store_record_value` | No | `""` | Record value (SECRET — set from a `no_log` fact) for `record_write`. |
| `cluster_pb_store_record_note` | No | `""` | Optional note stored with a written record. |
| `cluster_pb_store_record_id` | No | `""` | Record id for the by-id primitives. |
| `cluster_pb_store_record_fields` | No | `{}` | Field → value map for `record_patch_fields` (SECRET). |
`get_sybers.cluster.cluster_secrets` (via `tasks_from: ludus_root_key`), included at the point of need in `auth_superuser.yml` rather than as a
`meta` dependency, so the ROOT-key claim is visible in the task list. No `meta/main.yml` dependencies.

```yaml
- name: Ensure the credentials collection, then write a record
  hosts: ludus_server
  become: true
  tasks:
    - name: Ensure gs_infra_credentials exists with the ruled API rules
      ansible.builtin.include_role:
        name: get_sybers.cluster.cluster_pb_store
    - name: Store a credential (value comes from a no_log fact)
      ansible.builtin.include_role:
        name: get_sybers.cluster.cluster_pb_store
        tasks_from: record_write
      vars:
        cluster_pb_store_record_name: RA.apikey
        cluster_pb_store_record_value: "{{ _some_no_log_fact }}"
```

The ensure-collection path (`main`) is convergent: it creates the collection only when absent and updates rules only when they have drifted,
then re-probes and asserts the desired end state — so a converged store is `changed=0`. The record primitives are explicit CRUD
(`record_write` creates, `record_update`/`record_patch_fields` mutate, `record_delete` removes) and are only as idempotent as the caller's use
of them; reads (`record_read*`, `record_list`) and the preflight change nothing.
