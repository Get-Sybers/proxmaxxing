> Reference notes for connecting Proxmox VE to an existing LDAP directory or Active
> Directory domain, so admins sign in with corporate credentials instead of
> local Proxmox accounts. Prose rewritten in my own words; commands and config
> values preserved for accuracy.
>
> Source: https://proxmoxpulse.com/articles/proxmox-ldap-active-directory-authentication/
- **Realm types** — Proxmox supports PAM, PVE, LDAP, Active Directory, and OIDC, each with a different trust model and sync behaviour.
- **Sync is optional** — you can authenticate against LDAP without pre-syncing users, but syncing lets you assign roles in the GUI and shows real usernames in the audit log.
- **Groups map to roles** — assign an AD group to a Proxmox role once, and every member inherits that permission at the given resource path.
- **Keep a local escape hatch** — always maintain a tested local `root@pam` or `admin@pve` account so you can get back in if LDAP becomes unreachable.
- **TLS is mandatory** — use LDAPS (port 636) or STARTTLS; plain LDAP on port 389 transmits credentials in cleartext.
A stock Proxmox install gives you `root@pam` (backed by Linux PAM) plus local users in Proxmox's own PVE database. That's fine for a single-node homelab, but it breaks down for a team or a multi-node cluster:
- Rotating passwords means manually touching every node and every user.
- There's no reliable way to tell which "admin" performed a given action.
- Onboarding and offboarding happen in Proxmox specifically, not through your identity provider.
LDAP integration fixes all three, and lets you reuse existing group structures — an "Infrastructure Admins" AD group becomes a Proxmox Administrator role assignment in seconds.
**Active Directory vs plain LDAP** — the realm type labelled "Active Directory" in the GUI is still LDAP underneath, but it pre-fills sensible defaults for Microsoft's schema (`sAMAccountName`, `DC=`-style base DN, a Kerberos realm field). For OpenLDAP, FreeIPA, or Authentik with an LDAP backend, use the generic "LDAP" realm type instead.
Gather these before opening the GUI:
- **LDAP server hostname** — a domain controller FQDN (AD) or your OpenLDAP address. Use the FQDN, not an IP, so TLS certificate validation works.
- **Base DN** — e.g. `DC=corp,DC=example,DC=com` (AD) or `dc=example,dc=org` (OpenLDAP).
- **Bind account** — a read-only service account (e.g. `svc-proxmox`) that can read users and groups. Don't use a Domain Admin.
- **Bind account DN or UPN** — e.g. `svc-proxmox@corp.example.com` (UPN format works well for AD).
- **Bind password** — stored encrypted by Proxmox under `/etc/pve/priv/`; still, use a long random password.
- **CA certificate** — the certificate chain in PEM format, if you're using LDAPS with a private CA.
Create the bind account on the AD side first:
```powershell
New-ADUser -Name "svc-proxmox" `
  -SamAccountName "svc-proxmox" `
  -UserPrincipalName "svc-proxmox@corp.example.com" `
  -Path "OU=Service Accounts,DC=corp,DC=example,DC=com" `
  -AccountPassword (ConvertTo-SecureString "YourLongRandomPassword!" -AsPlainText -Force) `
  -PasswordNeverExpires $true `
  -Enabled $true
```
Domain Users can read user and group objects by default, so a plain Domain User bind account is enough — no special delegation needed.
In the web UI, go to **Datacenter → Permissions → Authentication**. You'll see the default `pve` and `pam` realms. Click **Add** and pick **Active Directory Server** or **LDAP Server** depending on your directory.
For Active Directory, the form fields map like this:
| Field            | Example Value              | Notes                                               |
| ---------------- | -------------------------- | --------------------------------------------------- |
| Realm            | `corp`                     | Short name used at login: `user@corp`               |
| Base Domain Name | `corp.example.com`         | Proxmox derives the base DN automatically           |
| Server           | `dc01.corp.example.com`    | Use FQDN — required for TLS                          |
| Port             | `636`                      | LDAPS; use `389` + STARTTLS if LDAPS is unavailable |
| User Attribute   | `sAMAccountName`           | AD; use `uid` for OpenLDAP or FreeIPA               |
| Domain           | `corp.example.com`         | Kerberos realm field (AD only)                      |
| Bind User        | `svc-proxmox@corp.example.com` | UPN format works cleanly for AD                 |
| Bind Password    | `YourLongRandomPassword!`  | Stored encrypted in `/etc/pve/priv/`                |
For OpenLDAP or FreeIPA:
```yaml
Base DN:       dc=example,dc=org
Server:        ldap.example.org
Port:          636
User Attr:     uid
Bind DN:       cn=svc-proxmox,ou=serviceaccounts,dc=example,dc=org
Bind Password: YourLongRandomPassword!
```
If your LDAP server uses a cert signed by a private CA (almost always the case in enterprise AD), import that CA cert into Proxmox's trust store before saving the realm:
```bash
cp /path/to/corp-ca.pem /usr/local/share/ca-certificates/corp-ca.crt
update-ca-certificates
```
Proxmox then validates the LDAPS cert against the system trust store. Skip this and you'd have to disable certificate verification — tolerable in a homelab, never in production.
**Intermediate CA gotcha** — if your AD uses an intermediate CA, you need the full chain, not just the root. Export it from AD Certificate Services, SCP it to the node, and run `update-ca-certificates` again:
```powershell
certutil -ca.cert corp-ca-chain.crt
```
In the realm editor, open the **Sync** tab and set:
- **Sync Attributes** — `cn,mail,sAMAccountName` (AD) or `cn,mail,uid` (OpenLDAP)
- **User Classes** — `user` (AD) or `inetOrgPerson` (OpenLDAP)
- **Group Classes** — `group` (AD) or `groupOfNames` / `posixGroup` (OpenLDAP)
- **Group DN** — the OU holding your infra groups, e.g. `OU=Infra Groups,DC=corp,DC=example,DC=com`
Save the realm. If it reports a bind error on save, recheck the bind UPN and password — don't move on until it saves cleanly.
Run the first sync from the CLI; its output is more informative than the GUI's:
```bash
pveum realm sync corp --enable-new true --purge false --scope both
```
- `--scope both` — pulls users and groups
- `--enable-new true` — marks newly synced users as enabled in Proxmox
- `--purge false` — leaves existing Proxmox users in place if they vanish from LDAP (safer for a first run)
Expected output:
```
syncing realm 'corp'...
synced 47 users
synced 12 groups
done
```
Confirm under **Datacenter → Permissions → Users** (AD users appear with the `@corp` suffix) and **Datacenter → Permissions → Groups**.
Don't lean on manual syncs in production. Add a cron job:
```bash
0 */4 * * * root /usr/bin/pveum realm sync corp --enable-new true --purge false --scope both >> /var/log/proxmox-ldap-sync.log 2>&1
```
With `--purge false`, users removed from AD keep Proxmox access until you enable purge or disable them manually. Where offboarding is strict, add a weekly purge:
```bash
0 5 * * 0 root /usr/bin/pveum realm sync corp --purge true --scope users >> /var/log/proxmox-ldap-sync.log 2>&1
```
Assign roles to groups rather than individuals — Proxmox honours LDAP group membership for permission decisions.
Confirm the groups synced:
```bash
pveum group list
```
Then assign roles at the right resource path:
```bash
pveum acl modify / --group 'infra-admins' --role Administrator
pveum acl modify /pool/dev-pool --group 'dev-team' --role PVEVMAdmin
pveum acl modify / --group 'proxmox-readonly' --role PVEAuditor
```
Built-in roles worth knowing:
| Role                | What It Allows                                                           |
| ------------------- | ----------------------------------------------------------------------- |
| `Administrator`     | Full cluster access — treat like root for Proxmox operations            |
| `PVEAdmin`          | Manage VMs, storage, networks — no user or realm management             |
| `PVEVMAdmin`        | Full VM lifecycle — no node or storage administration                   |
| `PVEVMUser`         | Start, stop, and open console — no config changes                       |
| `PVEAuditor`        | Read-only view of the entire cluster                                    |
| `PVEDatastoreAdmin` | Manage backups and storage pools — handy for dedicated backup operators |
For anything these don't cover, create a custom role:
```bash
pveum role add StorageOperator \
  --privs "Datastore.Audit,Datastore.AllocateSpace,Datastore.AllocateTemplate"
```
Before telling the team, verify the full chain from the Proxmox host:
```bash
ldapsearch -H ldaps://dc01.corp.example.com \
  -D "svc-proxmox@corp.example.com" \
  -w "YourLongRandomPassword!" \
  -b "DC=corp,DC=example,DC=com" \
  "(sAMAccountName=testuser)" cn mail
```
A good bind returns `cn` and `mail` for the test user. Common errors:
- `ldap_bind: Invalid credentials (49)` — wrong bind DN or password
- `Can't contact LDAP server` — firewall blocking 636 or a DNS failure; test reachability:
```bash
nc -zv dc01.corp.example.com 636
```
- `TLS: hostname does not match` — the cert CN/SAN doesn't match the hostname you configured; use the FQDN that matches the cert
Then test interactively: log out of the GUI, pick the `corp` realm in the login dropdown, and sign in as a known AD user.
If realm config changes aren't taking effect, restart the daemon:
```bash
systemctl restart pvedaemon
```
The classic failure: the LDAP server goes unreachable or the bind password expires, and nobody can log in. This is exactly why you keep a local admin account live and tested.
```bash
pveum realm list
pveum realm modify corp --disable true
pveum realm modify corp --disable false
```
Common root causes:
1. **Bind account password expired** — check in AD:
```powershell
   Search-ADAccount -PasswordExpired -UsersOnly | Select-Object Name, PasswordExpiredAt
```
2. **Certificate expired** — check the LDAPS cert expiry from the host:
```bash
   echo | openssl s_client -connect dc01.corp.example.com:636 2>/dev/null \
     | openssl x509 -noout -dates
```
3. **Domain controller unreachable** — DNS change, firewall update, or DC maintenance.
4. **Realm config corrupted after an upgrade** — inspect `/etc/pve/domains.cfg` for garbled entries; it's plain text and editable.
Note: active sessions survive an LDAP outage, since Proxmox doesn't re-validate session tokens against LDAP on every request. Anyone already logged in keeps working until their session times out (default 2 hours); only new logins fail.
Proxmox's LDAP/AD integration removes the burden of per-admin Proxmox passwords, and setup runs under 30 minutes once you have the bind account and base DN ready. Three habits keep it reliable: a tested local fallback account, LDAPS with verified certificates in production, and scheduled sync jobs rather than ad-hoc manual runs. With AD groups mapped to roles, onboarding becomes a matter of adding someone to the right security group — Proxmox picks it up on the next sync.
