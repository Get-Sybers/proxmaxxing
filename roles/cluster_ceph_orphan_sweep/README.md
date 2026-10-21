Reaps orphaned Ceph RBD disks left on the guest RBD pool (`ceph_pool`) by `cfs-lock`-timed-out
`qmdestroy` calls: a destroy that times out on the cluster lock removes the guest configuration but
leaves its `vm-<id>-disk-<n>` images on the pool, where nothing references them any more.
**Irreversible. Previews by default.** An `rbd rm` cannot be undone; the review of
the "Would remove" list is the only rollback.
On a **Proxmox cluster node** (the master node) — it needs `rbd`, `pvesh`
and `ceph`. Every host-touching task in the role (and every check in the included
`cluster_preflight`) carries `delegate_to: {{ cluster_ceph_orphan_sweep_delegate_to }}`,
default `localhost` — the ansible **controller**, which is the master node in both
sanctioned contexts. That delegation is what makes the role drivable both ways:
**1. From the client, via `ludus range deploy`** (needs a built range). Stock Ludus
applies user-defined roles ON the range VM (`hosts: <vm_name>` in the generated
play) and `--only-roles` only *filters* the roles already named in the range
config — so the role must be listed in a config VM's `roles:` (the FGNW config
carries it on the `attacker` VM as its maintenance carrier), and the delegation
moves execution off that VM onto the controller, the master node:

```bash
ludus ansible collection add https://github.com/Get-Sybers/proxmaxxing.git --global --force
ludus range deploy --only-roles get_sybers.cluster.cluster_ceph_orphan_sweep -t user-defined-roles
```

Caveats: the user-defined-roles stage fails at stock Ludus's *"\<vm\> is not in the
Ansible inventory"* gate if **any** role-bearing config VM is unbuilt — so this
path needs the range deployed; and because the role sits in the config, every
**full** deploy also runs it (harmless: preview by default, a read-only orphan
report — but its preflight failing, e.g. Ceph CLI unreachable, would fail that
deploy).
**2. On the server, via the wrapper playbook** — the fallback for the 0-VM
teardown window (`delegate_to: localhost` resolves to the same node, the master):

```bash
cd /opt/ludus/users/<user>/.ansible/collections/ansible_collections/get_sybers/cluster
ansible-playbook -i inventories/cluster playbooks/cluster-ceph-orphan-sweep.yml
ansible-playbook -i inventories/cluster playbooks/cluster-ceph-orphan-sweep.yml -e cluster_ceph_orphan_sweep_preview_only=false
```

**Flipping preview→apply via `range deploy`** (it has no `-e`): set
`cluster_ceph_orphan_sweep_preview_only: false` in the carrier VM's `role_vars` (or in
`global_role_vars`) — stock Ludus `set_fact`s both onto the VM's host context at
the user-defined-roles stage, and the role reads them there — push the config
(`ludus range config set`), run the `--only-roles` deploy, then **revert the
config immediately**: a config left on `false` would make every later full
deploy apply the sweep silently.

1. **name** is exactly `^vm-<id>-disk-<n>` — never a `base-*` template, and never a
   snapshot RAM-state (`-state-`), cloudinit or fleece volume.
2. **no live guest config references it** — no live QEMU VM *or* LXC container config uses it, regardless of whether its
   VMID tag is live. Fail-closed: an empty guest list, a dropped guest, an
   unreadable config, or an extraction that does not yield real image names all
   abort the sweep before anything is touched.
3. **zero RBD watchers** — a *runtime* backstop. A mapped disk has a watcher; a
   powered-off guest does not, so this protects running guests but is **not** the
   logic gate. Gate 2 is what protects a stopped range.
| variable | default | meaning |
|---|---|---|
| `cluster_ceph_orphan_sweep_pool` | `{{ ceph_pool }}` | the RBD pool to sweep (the inventory's guest pool; constrained to safe chars) |
| `cluster_ceph_orphan_sweep_preview_only` | `true` | report only; set `false` to actually `rbd rm` |
| `cluster_ceph_orphan_sweep_delegate_to` | `localhost` | execution host for every host-touching task, preflight included; the default is the controller (the master node in both sanctioned contexts) |
None for the removal — it is `rbd rm`. The preview run and `--check` are the review
that stands in for a rollback. Read the candidate list before opting in.
Delete RBD volumes via the Proxmox storage API by hand — that goes through the very
`cfs-lock` that stranded them, and bypasses these gates.
