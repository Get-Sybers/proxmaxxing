Fills the host network values of the Ludus server `config.yml` from the live node, so `gather_facts` sets them rather than you typing them by hand. It
reads the node's default IPv4 route (interface, address, netmask, gateway) from the gathered facts and writes
`host_vars/<host>/ludus_net.yml` — the file `host_vars/<host>/ludus_config.yml` references for `proxmox_interface`, `proxmox_local_ip`,
`proxmox_public_ip`, `proxmox_gateway` and `proxmox_netmask`. The rest of `ludus_config` is desired state you set in `group_vars/all/ludus.yml`
(the `ludus_cfg_*` building blocks) and the cross-references already in the inventory.

By default it writes a **proposal** under `inventory/discovered/host_vars/<host>/ludus_net.yml` (which Ansible never loads) so you can diff it before
adopting; `cluster_ludus_config_discover_write=in_place` rewrites the record in the inventory itself. Those network keys are reconciled onto
`/opt/ludus/config.yml` by `cluster_ludus_install` only when `cluster_ludus_install_manage_network=true` (run-sheet caution C1), so an empty or
proposal-only record never restyles the working network.

- **Privilege:** runs the `cluster_preflight` gate (root + a PVE node); the fact gather is read-only. The only write is the inventory file, on the controller.
- **Collections:** `ansible.builtin` only. **Min ansible:** 2.19. **Platforms:** Debian (bookworm, trixie).

| Variable | Required | Default | Description |
| --- | --- | --- | --- |
| `cluster_ludus_config_discover_write` | No | `additional` | `additional` writes a proposal under `inventory/discovered/`; `in_place` rewrites `host_vars/<host>/ludus_net.yml`. |
| `cluster_ludus_config_discover_inventory_dir` | No | `{{ inventory_dir }}` | Inventory directory the record is written under. |
| `cluster_ludus_config_discover_delegate_to` | No | `localhost` | The host holding the inventory checkout the record is written to. |
| `cluster_ludus_config_discover_backup` | No | `false` | Keep a timestamped backup beside a file rewritten in place. |

```sh
ansible-playbook playbooks/ludus-config-discover.yml                                    # proposal under inventory/discovered/ — diff, then adopt
ansible-playbook playbooks/ludus-config-discover.yml --check --diff                     # what would be written, nothing changed
ansible-playbook playbooks/ludus-config-discover.yml -e cluster_ludus_config_discover_write=in_place   # rewrite the record here
```
