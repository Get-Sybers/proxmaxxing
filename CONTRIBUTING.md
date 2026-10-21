# Contributing

## Pull requests

Changes to this project are proposed as pull requests on GitHub at
<https://github.com/get-sybers/proxmaxxing>. A pull request is reviewed there
and, once green on `all_green`, merged into `main`.

The branch ruleset (`.github/rulesets/main.json`) requires the CI workflow's
`all_green` status check (prek over every file, the must-have files, the lane
plan, ansible-lint, the pin discipline, sanity, the changelog lint, the build
and the Molecule lanes), dismisses stale reviews on push, and asks an extra
approval for commits not attributed to the pull request's author; it sets no
approval count of its own and allows merge, squash and rebase merges.
Branches are named `<type>/<description>` (`feat/ceph-mesh-bench`); the pull
request title is a Conventional Commit (`feat(cluster_discover): …`,
`fix(playbooks): …`), because a squash merge uses it as the commit message.

## Before you open one

```sh
make deps        # the pinned collections and the test tooling
prek install     # the git hooks: lint, secrets, commit-msg
make conform     # the full local gate: lint, pins, sanity, molecule, changelog, build
```

`make conform` runs the same commands CI runs, with the same configuration
files, so what passes locally passes on the pull request. Every change that
touches a plugin needs a fragment under `changelogs/fragments/`; a change to
behaviour or an interface updates the documentation under `doc/`, the inventory
README and the role's `README.md`.

## Site configuration stays out of the repository

The repository carries only `inventory/example/`, the template of the site
configuration; `make config` copies it into `inventory/`, where the real files
are untracked. A pull request never adds a node name, an address, a pool, a
zone, a serial or a credential: a new input gets a `CHANGE-ME` placeholder in
the template and a sentence in the inventory README. The example nodes are
`pi-01`, `pi-02` and `pi-03`; example addresses use the RFC 5737 documentation
ranges (`192.0.2.0/24` for the management LAN, `198.51.100.0/24` and
`203.0.113.0/24` for the storage networks). The As-Is records
(`host_vars/<host>/node.yml`, `group_vars/proxmox_cluster/cluster.yml`) are
skeletons that `playbooks/cluster-discover.yml` fills on the operator's copy,
never in the template.

## The standards

[`doc/standards/`](doc/standards/02-Ansible-Standards.md) carries the house
rules every role and play is held to: a role performs actions and a playbook
decides which run, every value arrives through the native variable system,
every task is idempotent and honest about change. The CI workflow and the
linting and conformance gate are the standards' own
([`03`](doc/standards/03-ansible-ci-workflow.md),
[`04`](doc/standards/04-Linting-and-Conformance.md)). A change that needs an
exception to a rule is discussed in the pull request, never waived in the code.

## License and copyright

By default, any contribution to this project is made under the GNU Affero
General Public License v3.0 only (`AGPL-3.0-only`, see `LICENSE`). The author
of a change remains the copyright holder of their contribution; there is no
copyright assignment.

## Security

Do not open a public issue for a security problem. Use
**Security → Report a vulnerability** on the repository; see `SECURITY.md`.
