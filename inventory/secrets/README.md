# inventory/secrets/

Gitignored, `ansible-vault`-encrypted per-host/per-topic secret files. Nothing here is committed except this README, the `.gitignore`, and
`*.example` templates (standards §7, the split vars/vault pattern). `ansible.cfg` excludes this directory from inventory parsing, so a file
here is only ever loaded with `-e @inventory/secrets/<topic>.yml --ask-vault-pass` (or a `--vault-password-file`).

No play in this collection takes a vaulted `-e` file: the credentials the plays handle live in the house credential store on the master
node (the encrypted ZFS vault and the PocketBase records, see `group_vars/all/credentials.yml`), and the PVE API credential comes from
the `PROXMOX_*` environment. The 1Password mirror that did take one lives in
[get-sybers/lxc](https://github.com/get-sybers/lxc) with its `secrets/onepassword.yml.example`.
