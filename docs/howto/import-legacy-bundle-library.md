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
sudo chown -R <django-user>:<django-group> /srv/c-lara/legacy-bundles
```

From your laptop, copy the downloaded bundle directory tree to the server. For example:

```bash
rsync -av --progress /path/on/laptop/adelaide_legacy_bundles/ \
  <server-user>@<server-host>:/srv/c-lara/legacy-bundles/adelaide/
```

Replace:

- `/path/on/laptop/adelaide_legacy_bundles/` with the folder on your laptop;
- `<server-user>` and `<server-host>` with your SSH details;
- `/srv/c-lara/legacy-bundles/adelaide/` with the chosen server path.

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

For production, add these variables to the same place where the C-LARA-2 service environment is configured, then restart the Django application service. The important point is that the running web process must see these variables.

## Step 3: build the global metadata file

On the server, from the repository root, run:

```bash
cd /path/to/C-LARA-2/platform_server
python manage.py build_legacy_bundle_metadata /srv/c-lara/legacy-bundles/adelaide
```

This creates:

```text
/srv/c-lara/legacy-bundles/adelaide/legacy_bundle_metadata.json
```

The command scans immediate child directories, reads each child `metadata.json`, and writes a global file with a `bundles` list. It also records import paths so the web UI can import the selected bundle.

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

The selected bundle is imported as a new C-LARA-2 project using the same source/legacy ZIP importer as the ordinary upload flow.

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

Check that the running Django process has:

```bash
echo $C_LARA_LEGACY_BUNDLE_LIBRARY_ROOT
```

If you added the variable to a service environment file, restart the web service.

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

### Permission denied or missing files

Ensure the OS user running Django can read the bundle library:

```bash
sudo chown -R <django-user>:<django-group> /srv/c-lara/legacy-bundles
sudo chmod -R u+rwX /srv/c-lara/legacy-bundles
```

### You only have the bundle library on your laptop

Either copy it to the server with `rsync` as described above, or use the local upload section to import one ZIP at a time from your laptop.
