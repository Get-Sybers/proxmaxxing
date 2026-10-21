# How-to guides

Step-by-step guides for the operations this collection is used for. Each one lives beside the thing it describes.

| Guide | When |
| --- | --- |
| [Configure a cluster](../../inventory/README.md) | First run: `make config`, replace every `CHANGE-ME`, name the nodes, write the desired state (links, mesh, Ceph, SDN). |
| [Discover the cluster](../../roles/cluster_discover/README.md) | Fill or refresh the As-Is records (`node.yml`, `cluster.yml`) from the live cluster; drift report and drift gate. |
| [Run the plays from a container](../../container/README.md) | Drive the SSH-based cluster plays, `--syntax-check` and lint from the reproducible controller image instead of a workstation install. |
| [Install and reconcile the Ludus server](../../roles/cluster_ludus_install/README.md) | Stand up Ludus on the master node, or converge the SAFE keys of its `config.yml` for this cluster. |
| [Hold and prove a Ludus API key](../../roles/cluster_ludus_auth/README.md) | Authenticate an identity from the PocketBase credential store, persist the key for the CLI, rotate it. |
| [Sweep orphaned Ceph disks](../../roles/cluster_ceph_orphan_sweep/README.md) | Preview, then remove, the RBD images a timed-out `qmdestroy` left on the guest pool. |
| [Keep local Ludus patches after an update](../../roles/cluster_patch_ludus/README.md) | Re-apply the local patches `ludus-server --update` reverts, and the packer plugins and ISO links beside them. |
