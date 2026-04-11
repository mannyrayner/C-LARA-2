# Clone a project snapshot

Use this workflow to create a new project that copies:

- project-level fields (title, description, source text, language options, model/settings),
- persisted source files,
- the latest available version of each run artifact file.

This is useful for taking a snapshot before further processing and comparing outcomes.

## Steps

1. Open the project detail page.
2. Optionally edit **Clone name** (default is `<current-name> (Clone)`).
3. Click **Clone project**.
4. Confirm.

Result:

- A new project is created with title suffix `(Clone)` (or `(Clone) (2)`, etc, if needed).
- Latest run files are copied into a new run directory under the cloned project.
- Image assets and image-stage DB rows are copied to the cloned project.
- If compiled output exists in copied files, the clone keeps a working `compiled_path`.

## Notes

- Clone action is owner-only.
- Cloning does not delete or modify the original project.
