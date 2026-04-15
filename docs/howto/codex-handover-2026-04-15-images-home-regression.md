# Codex Handover: `project_images_home` pivot-language regression

_Date: 2026-04-15_

## Why this handover exists

A repeated regression has been reported in `platform_server/projects/views.py` inside
`project_images_home`:

- `pivot_language` referenced before assignment
- `valid_pivot_languages` referenced while not defined in the active branch
- Mixed old/new code path where translation toggle logic and legacy pivot-language validation coexist

The user reports that PR descriptions were correct but merged diff content did not consistently match the requested edit, indicating likely branch/thread drift.

## Recommendation

Yes: **start a fresh Codex thread** for C-LARA-2 and use this file as the handover seed.

This issue is small and deterministic; a clean thread should reduce state drift risk and make review easier.

## Required functional intent

For `project_images_home` POST handling:

1. Keep handling for `generate_page_images_from_translations`.
2. Save `project.page_image_text_source`.
3. Sync page rows via `_ensure_project_page_rows(project)`.
4. **Do not** keep legacy pivot-language validation unless the branch explicitly supports it end-to-end.

If pivot-language behavior is retained in a branch, then:

- derive `pivot_language` from project glossing/target language,
- and ensure both variable definition and any validation variables are present in the same block.

## Minimal safe target block (no pivot validation)

```python
if request.method == "POST":
    from_translations = (request.POST.get("generate_page_images_from_translations") or "").strip().lower() in {
        "1",
        "true",
        "on",
        "yes",
    }
    text_source = (
        Project.PAGE_IMAGE_TEXT_SOURCE_TRANSLATION
        if from_translations
        else Project.PAGE_IMAGE_TEXT_SOURCE_SEGMENTATION
    )
    allowed_text_sources = {choice[0] for choice in Project.PAGE_IMAGE_TEXT_SOURCE_CHOICES}
    if text_source not in allowed_text_sources:
        messages.error(request, "Unknown page-image text source option.")
    else:
        project.page_image_text_source = text_source
        project.save(update_fields=["page_image_text_source", "updated_at"])
        synced = _ensure_project_page_rows(project)
        messages.success(request, f"Saved image settings and synced {synced} page rows.")
    return redirect("project-images-home", pk=project.pk)
```

## Verification checklist for the new thread

Run these commands from repo root:

```bash
rg -n "def project_images_home|pivot_language|valid_pivot_languages|selected_image_generation_pivot_language|image_generation_pivot_language" platform_server/projects/views.py platform_server/projects/templates/projects/project_images_home.html
python3 platform_server/manage.py test projects.tests.test_image_pages
python3 platform_server/manage.py makemigrations --check --dry-run
```

Expected outcome:

- no stale pivot-language references in active view/template (except historical migration files if searched globally),
- `test_image_pages` passes,
- no model drift in `makemigrations --check --dry-run`.

## Suggested acceptance criteria

- Posting `/projects/<pk>/images/` with and without `generate_page_images_from_translations` succeeds.
- No `NameError` for `pivot_language` or `valid_pivot_languages`.
- `project.page_image_text_source` toggles correctly and page rows are synced.

## Notes for reviewer

If a PR description claims removal of pivot-language validation, confirm the diff in
`platform_server/projects/views.py` actually removes both:

- `pivot_language` references, and
- `valid_pivot_languages` branch.

Do not accept if only one side is removed.
