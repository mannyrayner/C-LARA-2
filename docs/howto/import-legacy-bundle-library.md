# Importing legacy C-LARA bundles from a server-side library

This guide explains how to use the enhanced **Import from ZIP** workflow to import legacy C-LARA JSON bundles into C-LARA-2 projects.

It is intended for the current Adelaide legacy-export use case, where you have a folder containing many downloaded legacy bundle directories. Each bundle directory is named by project number and contains a top-level `metadata.json` file, for example:

```json
{
  "id": 9,
  "title": "Ørberg's Deutsch",
  "l2": "german",
  "l1": "english",
  "owner_username": "jeremiahmcpadden",
  "size_bytes": 4044,
  "sha256": "d32ff4d5ab8a69d4d0d9766dde66b54569e9533f94f5176830cd3b5c8e395367"
}
```

## Important: where the bundle library must live

The searchable library import mode reads files from the **C-LARA-2 server filesystem**.

If your legacy C-LARA bundle library is currently on your laptop but you want the imported projects to be created on the server, you first need to copy or sync the bundle library to the server. The browser UI does not let the server browse folders on your laptop.

There are two options:

1. **One-off local upload:** use the simple local ZIP upload mode in **Projects → Import from ZIP**. This works from your laptop, but imports one ZIP at a time.
2. **Searchable server-side library:** copy the full bundle-library folder to the server, configure C-LARA-2 to point at it, build the global metadata file, then use the admin-only searchable import menu.

The rest of this guide describes option 2.

## Step 1: copy the library to the server

Choose a server-side location readable by the Django process, for example:

```bash
sudo mkdir -p /srv/c-lara/legacy-bundles/adelaide
```

### Determine the Django user/group

On the current AWS deployment, the repo is expected to live at `/srv/C-LARA-2`, the app environment file at `/etc/clara2.env`, and the services are named `gunicorn-clara2` and `djangoq-clara2` (see [server-admin-tasks.md](server-admin-tasks.md)). The existing media-permissions runbook uses `ubuntu:www-data`, so those are plausible values, but check the live server before running `chown`.

Useful checks on the server:

```bash
# Check whether systemd explicitly sets a service user/group.
sudo systemctl show gunicorn-clara2 -p User -p Group
sudo systemctl show djangoq-clara2 -p User -p Group

# Check the actual running processes.
ps -eo user,group,comm,args | grep -E 'gunicorn|qcluster|manage.py' | grep -v grep

# Check ownership used by existing C-LARA-2 media files.
stat -c '%U:%G %n' /srv/C-LARA-2/platform_server/media
```

If these commands show `ubuntu` and `www-data`, use:

```bash
sudo chown -R ubuntu:www-data /srv/c-lara/legacy-bundles
sudo find /srv/c-lara/legacy-bundles -type d -exec chmod 2775 {} \;
sudo find /srv/c-lara/legacy-bundles -type f -exec chmod 664 {} \;
```

If the commands show a different service user or group, substitute those values. The key requirement is that the web service and any background worker that may import bundles can read the folder and files.

### Copy from your laptop

From your laptop, copy the downloaded bundle directory tree to the server. For example:

```bash
rsync -av --progress /path/on/laptop/adelaide_legacy_bundles/ \
  <ssh-user>@c-lara-2.c-lara.org:/srv/c-lara/legacy-bundles/adelaide/
```

For the Adelaide corpus upload that was successfully completed on AWS, the working command used the EC2 private-key file explicitly and enabled safer resume behaviour for a large transfer:

```bash
rsync -avh --progress --partial --append-verify \
  -e "ssh -i /home/CLARA2/EC2KeyPairForClara2.pem" \
  /home/CLARADownloadedProjectsFromServer_v2/ \
  ubuntu@c-lara-2.c-lara.org:/srv/c-lara/legacy-bundles/adelaide/
```

Keep the private key on the uploading machine only; do not commit it to this repository. SSH will usually reject an overly readable key, so if needed run `chmod 600 /home/CLARA2/EC2KeyPairForClara2.pem` before retrying.

Replace:

- `/path/on/laptop/adelaide_legacy_bundles/` with the folder on your laptop;
- `<ssh-user>` with the Linux/SSH account you use to administer the AWS host;
- `/srv/c-lara/legacy-bundles/adelaide/` with the chosen server path.

Do **not** infer the SSH username from the website URL. `https://c-lara-2.c-lara.org/` is the browser URL for the web application; SSH uses a separate Linux account. For the AWS setup documented elsewhere in this repo, `ubuntu` is a common candidate, so the command may be:

```bash
rsync -av --progress /path/on/laptop/adelaide_legacy_bundles/ \
  ubuntu@c-lara-2.c-lara.org:/srv/c-lara/legacy-bundles/adelaide/
```

If DNS/SSH is configured differently, your server admin notes may instead specify another host or user. Use the same `<ssh-user>@<ssh-host>` pair that you use for normal server maintenance.

### If `rsync` times out on port 22

A failure like this means `rsync` could not even open the SSH connection to the server:

```text
ssh: connect to host c-lara-2.c-lara.org port 22: Connection timed out
rsync: connection unexpectedly closed (0 bytes received so far) [sender]
rsync error: error in rsync protocol data stream (code 12)
```

In this case, the `rsync` error code is only a follow-on symptom. Debug SSH connectivity first; do not spend time changing C-LARA-2 passwords or Django settings yet. A timeout is different from `Permission denied (publickey)`: a timeout usually means that traffic to TCP port 22 is blocked, routed to the wrong host, or not being answered.

Run these checks from the same laptop/WSL shell where `rsync` failed:

```bash
# Confirm that the hostname resolves to the IP address you expect.
getent hosts c-lara-2.c-lara.org
# If getent is not available, try one of these instead.
nslookup c-lara-2.c-lara.org
dig c-lara-2.c-lara.org

# Check whether TCP port 22 is reachable at all.
nc -vz -w 10 c-lara-2.c-lara.org 22

# Ask SSH for verbose connection diagnostics.
ssh -vvv -o ConnectTimeout=10 ubuntu@c-lara-2.c-lara.org
```

Interpret the results as follows:

- If hostname lookup fails or returns an unexpected IP address, use the real SSH hostname/IP from the AWS console or server-admin notes instead of `c-lara-2.c-lara.org`. The browser hostname and SSH hostname are not guaranteed to be the same.
- If `nc` or `ssh` times out, check the AWS security group/firewall. The instance must allow inbound TCP port 22 from your current public IP address, or you must connect through the documented VPN/bastion host. This was the cause of the first Adelaide upload failure: the EC2 inbound security rule had to be adjusted before `rsync` could connect. Prefer a narrow rule for your current IP address rather than opening SSH broadly. Home and university networks can also block outbound SSH; try a different network or ask your network admin.
- If `ssh -vvv` reaches the server and then says `Permission denied (publickey)`, port 22 is reachable and the remaining problem is SSH credentials/keys. For the Adelaide AWS upload, the fix was to pass the EC2 key with `-e "ssh -i /home/CLARA2/EC2KeyPairForClara2.pem"`. See the next section.
- If SSH uses a non-standard port, include it in both SSH and `rsync`. For example:

```bash
ssh -p <ssh-port> ubuntu@<ssh-host>
rsync -av --progress -e 'ssh -p <ssh-port>' CLARADownloadedProjectsFromServer_v2/ \
  ubuntu@<ssh-host>:/srv/c-lara/legacy-bundles/adelaide/
```

If you have access to the AWS host through another route, also check on the server that SSH is running and listening:

```bash
sudo systemctl status ssh
sudo ss -tlnp | grep ':22'
```

After plain `ssh ubuntu@<ssh-host>` succeeds, retry the original `rsync` command.

### Passwords and SSH keys

You should **not** use your C-LARA-2 web-app password, Django admin password, or GitHub password for `rsync`/SSH. `rsync` over SSH authenticates to the server's Linux account.

Typical AWS hosts use SSH keys. In that case:

- you may not be prompted for a password at all;
- you may be prompted for your local SSH private-key passphrase, if your key has one;
- if you see `Permission denied (publickey)`, your laptop is not using an SSH key accepted by the AWS account.

If the server has password-based SSH enabled, use the password for the Linux account named by `<ssh-user>`. If you do not know that password or key, ask whoever administers the AWS host rather than guessing.

After copying, verify on the server that the top-level directory contains numbered bundle directories, each with its own `metadata.json`:

```bash
find /srv/c-lara/legacy-bundles/adelaide -maxdepth 2 -name metadata.json | head
```

## Step 2: configure C-LARA-2

Set the environment variable `C_LARA_LEGACY_BUNDLE_LIBRARY_ROOT` for the C-LARA-2 server process:

```bash
export C_LARA_LEGACY_BUNDLE_LIBRARY_ROOT=/srv/c-lara/legacy-bundles/adelaide
```

Optionally set the metadata filename/path. If omitted, C-LARA-2 uses `legacy_bundle_metadata.json` inside the library root.

```bash
export C_LARA_LEGACY_BUNDLE_LIBRARY_METADATA=legacy_bundle_metadata.json
```

For production, add these variables to the same place where the C-LARA-2 service environment is configured, then restart the Django application service. The important point is that the running web process must see these variables. Running `export C_LARA_LEGACY_BUNDLE_LIBRARY_ROOT=...` in an SSH shell only affects commands started from that shell; it does **not** update an already-running Gunicorn/Django process.

On the current AWS setup, check `/etc/clara2.env` first. If that is the service environment file, add or update these lines there:

```bash
C_LARA_LEGACY_BUNDLE_LIBRARY_ROOT=/srv/c-lara/legacy-bundles/adelaide
C_LARA_LEGACY_BUNDLE_LIBRARY_METADATA=legacy_bundle_metadata.json
```

Then restart the web service, and the background worker if it also needs the setting:

```bash
sudo systemctl restart gunicorn-clara2
sudo systemctl restart djangoq-clara2
```

## Step 3: build the global metadata file

On the server, from the repository root, run the command as a Linux user that can write to the library root. On the current AWS setup this is normally `ubuntu`:

```bash
cd /srv/C-LARA-2/platform_server
/srv/C-LARA-2/.venv/bin/python manage.py build_legacy_bundle_metadata /srv/c-lara/legacy-bundles/adelaide
```

If you are logged in as a different administration account, explicitly run the command as `ubuntu` rather than relying on the active shell user:

```bash
cd /srv/C-LARA-2/platform_server
sudo -u ubuntu /srv/C-LARA-2/.venv/bin/python manage.py build_legacy_bundle_metadata /srv/c-lara/legacy-bundles/adelaide
```

This creates:

```text
/srv/c-lara/legacy-bundles/adelaide/legacy_bundle_metadata.json
```

The command scans immediate child directories, reads each child `metadata.json`, and writes a global file with a `bundles` list. If a child directory contains a ZIP such as `source.zip`, the metadata records that ZIP as the import payload while keeping the sibling `metadata.json` path. The admin import flow treats this as one legacy bundle: it opens `source.zip` and injects the sibling `metadata.json` into the temporary import ZIP when the inner ZIP contains flat or single-root `annotated_text.json` but no metadata file of its own.

If you want to write the global metadata file somewhere else inside the same library root, use:

```bash
python manage.py build_legacy_bundle_metadata /srv/c-lara/legacy-bundles/adelaide \
  --output metadata/all_bundles.json
```

Then configure:

```bash
export C_LARA_LEGACY_BUNDLE_LIBRARY_METADATA=metadata/all_bundles.json
```

## Step 4: use the admin-only import UI

1. Log in to C-LARA-2 as a staff/admin user.
2. Open **Projects**.
3. Click **Import from ZIP**.
4. Use the top section, **Upload a local ZIP**, for ordinary one-off uploads.
5. Use the admin-only section, **Import from configured legacy bundle library**, to search the server-side library.
6. Search by any combination of:
   - title substring;
   - owner/user substring;
   - source/L2 language;
   - target/L1 language.
7. Select a bundle from the menu.
8. Click **Import selected bundle**.

The selected bundle is imported as a new C-LARA-2 project using the same source/legacy ZIP importer as the ordinary upload flow. For Adelaide-style directories containing `metadata.json` plus `source.zip`, the server-side importer combines those two files in memory before invoking the legacy importer; it does not require you to manually unzip or repackage each directory.

## What gets imported

For supported legacy JSON bundles, C-LARA-2 imports:

- `annotated_text.json` and `metadata.json`;
- legacy audio/image files under the new project's `legacy_clara/` artifact folder;
- converted C-LARA-2 stage JSON artifacts;
- available image/style/page metadata;
- diagnostics for unsupported legacy content where applicable.

Imported projects are normal C-LARA-2 projects and can be inspected from the project detail page.

## Safety and access control

- The server-side library picker is shown only to staff/admin users.
- The configured metadata file must be inside the configured library root.
- Bundle paths from the metadata file are resolved relative to the configured root and rejected if they escape that root.
- The current implementation imports one selected bundle at a time. Multi-select/batch import with heartbeat-style progress is planned as a later extension.

## Troubleshooting

### The admin library section says the root is not configured

If the Import from ZIP page says:

```text
Library unavailable: Legacy bundle library root is not configured.
```

but `legacy_bundle_metadata.json` exists on disk, the most likely cause is that the environment variable was exported only in your interactive SSH shell. The website is served by the already-running Gunicorn/Django service, which has its own environment and will not see that shell export.

Use the new admin-only **Legacy library diagnostics** expander on the Import from ZIP page. If `Django setting LEGACY_CLARA_BUNDLE_LIBRARY_ROOT` is empty, configure the service environment file and restart Gunicorn. On the AWS deployment this is probably:

```bash
sudoedit /etc/clara2.env
# Add or update:
# C_LARA_LEGACY_BUNDLE_LIBRARY_ROOT=/srv/c-lara/legacy-bundles/adelaide
# C_LARA_LEGACY_BUNDLE_LIBRARY_METADATA=legacy_bundle_metadata.json

sudo systemctl restart gunicorn-clara2
sudo systemctl restart djangoq-clara2
```

Useful checks:

```bash
# Shows variables in your current shell only; this is not enough for the website.
echo "$C_LARA_LEGACY_BUNDLE_LIBRARY_ROOT"

# Shows whether systemd knows about the service environment file.
sudo systemctl cat gunicorn-clara2
sudo systemctl show gunicorn-clara2 -p Environment -p EnvironmentFiles

# After restart, inspect recent service logs if the page still reports an empty setting.
sudo journalctl -u gunicorn-clara2 -n 80 --no-pager
```

If the diagnostics show the root setting is present but the metadata path is missing, rebuild the metadata file or check `C_LARA_LEGACY_BUNDLE_LIBRARY_METADATA`.

### The metadata file is missing

Run:

```bash
cd /path/to/C-LARA-2/platform_server
python manage.py build_legacy_bundle_metadata /srv/c-lara/legacy-bundles/adelaide
```

Then reload the Import from ZIP page.

### No bundles match the filters

Try clearing all filters first. If the list is still empty, inspect the global metadata file and confirm it contains a non-empty `bundles` list:

```bash
python -m json.tool /srv/c-lara/legacy-bundles/adelaide/legacy_bundle_metadata.json | head -80
```

### Permission denied while building `legacy_bundle_metadata.json`

If Step 3 fails with an error like this:

```text
PermissionError: [Errno 13] Permission denied: '/srv/c-lara/legacy-bundles/adelaide/legacy_bundle_metadata.json'
```

the management command has successfully read the bundle directories, but the Linux user running `python manage.py ...` cannot create or overwrite the global metadata file in the library root. The most common gotcha is fixing ownership for `ubuntu:www-data` but then running the command as a different user that is neither `ubuntu` nor a member of `www-data`.

Check the actual command user, group membership, path permissions, and any existing metadata file:

```bash
whoami
id
namei -l /srv/c-lara/legacy-bundles/adelaide/legacy_bundle_metadata.json
ls -ld /srv/c-lara /srv/c-lara/legacy-bundles /srv/c-lara/legacy-bundles/adelaide
ls -l /srv/c-lara/legacy-bundles/adelaide/legacy_bundle_metadata.json 2>/dev/null || true
```

For the expected AWS deployment, repair the directory tree and then run the command as `ubuntu`:

```bash
sudo chown -R ubuntu:www-data /srv/c-lara/legacy-bundles
sudo find /srv/c-lara/legacy-bundles -type d -exec chmod 2775 {} \;
sudo find /srv/c-lara/legacy-bundles -type f -exec chmod 664 {} \;

cd /srv/C-LARA-2/platform_server
sudo -u ubuntu /srv/C-LARA-2/.venv/bin/python manage.py build_legacy_bundle_metadata /srv/c-lara/legacy-bundles/adelaide
```

If the metadata file already exists with awkward ownership or mode, remove it or repair it explicitly, then rerun the command:

```bash
sudo rm -f /srv/c-lara/legacy-bundles/adelaide/legacy_bundle_metadata.json
# or:
sudo chown ubuntu:www-data /srv/c-lara/legacy-bundles/adelaide/legacy_bundle_metadata.json
sudo chmod 664 /srv/c-lara/legacy-bundles/adelaide/legacy_bundle_metadata.json
```

### Permission denied or missing files during import

Ensure the OS user running Django can read the bundle library:

```bash
sudo chown -R <django-user>:<django-group> /srv/c-lara/legacy-bundles
sudo chmod -R u+rwX /srv/c-lara/legacy-bundles
```

### Importing a selected server bundle fails

If the bundle appears in the admin picker but the import fails after you click **Import selected bundle**, the picker and the importer have reached different stages of the workflow:

- the picker only needs to read the global `legacy_bundle_metadata.json`;
- the importer must also read the selected bundle directory or selected `source.zip`, combine a sibling `metadata.json` with the ZIP when needed, unpack that temporary ZIP safely, and convert the legacy JSON into C-LARA-2 project artifacts.

Common causes are:

1. **The metadata file is stale.** If you moved, renamed, or re-synced bundle directories after building `legacy_bundle_metadata.json`, rebuild it so the recorded `bundle_dir` values match the current filesystem.
2. **The configured root points at the wrong level.** `C_LARA_LEGACY_BUNDLE_LIBRARY_ROOT` should point at the directory whose immediate children are the numbered bundle directories, not at one individual bundle and not at the parent folder above the collection. For example, the root should normally contain paths like `9/metadata.json`, `10/metadata.json`, and so on.
3. **The metadata path is outside the configured root.** The import UI rejects metadata files and bundle paths that resolve outside `C_LARA_LEGACY_BUNDLE_LIBRARY_ROOT`, even if the OS could read them. Keep the global metadata file inside the library root, or set `C_LARA_LEGACY_BUNDLE_LIBRARY_METADATA` to a relative path such as `legacy_bundle_metadata.json` or `metadata/all_bundles.json`.
4. **Django can read the metadata file but not the bundle contents.** This can happen if `metadata.json` files are readable but audio, image, or nested JSON files were copied with more restrictive permissions. Re-run the ownership and permissions commands from Step 1, then retry.
5. **The bundle is incomplete or has an unexpected shape.** Each selected bundle should contain either a flat/rooted legacy ZIP with both `annotated_text.json` and `metadata.json`, or an Adelaide-style directory with sibling `metadata.json` and `source.zip` where `source.zip` contains flat or single-root `annotated_text.json`. If an `rsync` was interrupted, run it again and then verify the copied directory.
6. **There is not enough temporary or media storage.** Server-side imports create a temporary ZIP and then write project artifacts under the C-LARA-2 media/project area. Check available space if failures happen only on larger bundles.

If the page still reports `Bundle is missing project metadata`, copy the full `Import trace` appended to the error message. It records what the web process actually selected and opened: selected import path, source ZIP path, sidecar metadata path and existence, metadata entries injected into the temporary ZIP, `annotated_text.json` entries, `metadata.json` entries, detected legacy root, and the first ZIP entries.

Useful server-side checks:

```bash
# Confirm that the configured root is the collection directory.
find /srv/c-lara/legacy-bundles/adelaide -maxdepth 2 -name metadata.json | head

# Confirm that the global metadata points to bundle directories below that root.
python - <<'PY'
import json
from pathlib import Path
root = Path('/srv/c-lara/legacy-bundles/adelaide')
metadata = root / 'legacy_bundle_metadata.json'
data = json.loads(metadata.read_text(encoding='utf-8'))
for bundle in data.get('bundles', [])[:10]:
    bundle_dir = bundle.get('bundle_dir') or bundle.get('path')
    print(bundle.get('id'), bundle.get('title'), bundle_dir, (root / bundle_dir).exists() if bundle_dir else 'no path')
PY

# Check for the sidecar metadata and the contents of source.zip for one bundle.
ls -l /srv/c-lara/legacy-bundles/adelaide/1/metadata.json /srv/c-lara/legacy-bundles/adelaide/1/source.zip
zipinfo -1 /srv/c-lara/legacy-bundles/adelaide/1/source.zip | head -40

# Check for loose files if you are importing directory-shaped bundles.
find /srv/c-lara/legacy-bundles/adelaide -maxdepth 2 \
  \( -name metadata.json -o -name annotated_text.json \) | head -40

# Check disk space for temporary files and project media.
df -h /tmp /srv/C-LARA-2/platform_server/media
```

After fixing any of these issues, rebuild the metadata file and reload the Import from ZIP page:

```bash
cd /path/to/C-LARA-2/platform_server
python manage.py build_legacy_bundle_metadata /srv/c-lara/legacy-bundles/adelaide
```

### You only have the bundle library on your laptop

Either copy it to the server with `rsync` as described above, or use the local upload section to import one ZIP at a time from your laptop.
