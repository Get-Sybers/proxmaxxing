The template below is for bug reports and support questions. Remove what does
not apply and add what helps. Never paste a credential, a token, an API key or
a vaulted file.

# Required information

- Proxmox VE version (`pveversion`):
- `get_sybers.cluster` version (`ansible-galaxy collection list get_sybers.cluster`), or the branch and commit:
- `ansible-core` version (`ansible --version`):
- The play and the `-e` inputs you ran it with (values redacted where secret):
- The role involved (`roles/<name>`), when the failure is inside one:

# Issue description

A brief description of what failed or what could be improved.

# Steps to reproduce

1. Step one
2. Step two
3. Step three

# Information to attach

- [ ] the play output with `-vv` (secret-bearing tasks are `no_log` and print nothing)
- [ ] for a node-side play, the node's journal for the unit involved (`journalctl -u <unit> -n 200`)
- [ ] for a discovery or drift problem, the `cluster-discover.yml --check --diff` output (addresses redacted)
