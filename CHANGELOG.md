# Changelog

All notable changes to `get_sybers.cluster` are documented here. The format is
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and this project
follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html) (`0.y.z`
until the interface is stable).

`antsibull-changelog` generates this file from `changelogs/fragments/` at
release time; until the first release from this repository, the unreleased
notes live in the fragments. The `0.1.0` notes seeded into
`changelogs/changelog.yaml` predate this repository.

## [Unreleased]

### Added

- The `get_sybers.cluster` collection: the roles `cluster_preflight`,
  `cluster_discover`, `cluster_ludus_install`, `cluster_secrets`,
  `cluster_pb_store`, `cluster_ludus_auth`, `cluster_ceph_orphan_sweep`,
  `cluster_patch_ludus`, `cluster_patch_packer_iso`, `cluster_plugin_packer`
  and `sysmon_linux`; the `ceph_info` module and the `config_merge`,
  `config_drift` and `to_config_yaml` filters, with unit tests; the node-side
  plays (discovery, apt repositories, rolling upgrade, storage links, Ceph
  mesh, tuning, diagnosis and orphan sweep, SDN zone and VNets, Ludus server
  install) and the controller-side plays (audit logging, the credential vault
  with its invariant, migration and DEK rotation, the PocketBase credential
  store, the identity seats, the ghost9 PVE token, Ludus authentication and
  key rotation, default sources, packer ISO redirect, post-update reconcile);
  the containerised controller under `container/`. The fragments under
  `changelogs/fragments/` carry the detail.
- Molecule coverage on a digest-pinned Debian 13 container
  (`extensions/molecule/`): a negative scenario per role, and positive
  scenarios for `cluster_secrets` (`default`) and `cluster_discover`
  (`discover`).
- The site configuration template `inventory/example/`: `make config` copies
  it into `inventory/`, where the real files are untracked; the As-Is records
  are skeletons `playbooks/cluster-discover.yml` fills. Node names, addresses,
  pool and zone names, the cluster name and the owner's repositories are
  placeholders (`pi-01`/`pi-02`/`pi-03`, RFC 5737 addresses, `CHANGE-ME`,
  `cluster_slug`).
- The repository controls shared with the sibling collections: the CI
  workflow (prek over every file, the must-have files, lane planning with
  `scripts/molecule_lanes.py`, ansible-lint, pins, sanity, changelog, build,
  the Molecule lanes, `all_green`), the Links, Scorecard, Update pins and
  Release workflows, the branch and tag rulesets, Dependabot, CODEOWNERS,
  the community files and the house standards under `doc/standards/`.

[Unreleased]: https://github.com/get-sybers/proxmaxxing/compare/8ade96c...HEAD
