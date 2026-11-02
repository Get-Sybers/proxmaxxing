# inventory/secrets/

Gitignored, `ansible-vault`-encrypted per-host/per-topic secret files. Nothing here is committed except this README, the `.gitignore`, and
`*.example` templates (standards §7, the split vars/vault pattern). `ansible.cfg` excludes this directory from inventory parsing, so a file
here is only ever loaded with `-e @inventory/secrets/<topic>.yml --ask-vault-pass` (or a `--vault-password-file`).

Most credentials the plays handle live in the house credential store on the master node (the encrypted ZFS vault and the PocketBase
records, see `group_vars/all/credentials.yml`), and the PVE API credential comes from the `PROXMOX_*` environment. The one vaulted `-e`
file this collection reads is `ludus.yml` (`ludus.yml.example`): the Ludus `database_encryption_key`, split out of
the master's `host_vars/<master>/ludus_config.yml` under `vault_ludus_database_encryption_key`. Pass it to the install play with
`-e @inventory/secrets/ludus.yml --ask-vault-pass` (or a `--vault-password-file`); the role only *verifies* the running key against it and
never rewrites a live one. The 1Password mirror that also takes one lives in
[get-sybers/lxc](https://github.com/get-sybers/lxc) with its `secrets/onepassword.yml.example`.
