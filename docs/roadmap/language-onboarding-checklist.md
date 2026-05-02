# Roadmap: adding and maintaining supported languages

This checklist tracks all places that typically need updates when adding a new text/glossing language.

## Newly requested languages
- [x] Danish (`da`)
- [x] Norwegian (`no`)
- [x] Polish (`pl`)
- [x] Swedish (`sv`)

## Core updates (required)
- [x] Add language codes and display names to global language menu choices (`ProjectForm.LANGUAGE_CHOICES`).
- [x] Keep language-choice menus ordered alphabetically by display label, with **English first**.
- [ ] Add/update tests that assert expected language list contents and order.

## Pipeline and prompt updates (language-dependent)
- [ ] Add language-specific prompt templates/few-shots where needed (`prompts/<operation>/<language>/`).
- [ ] Verify fallback behavior for operations that currently rely on English templates.
- [ ] Add or validate language labels used in generated system prompts (e.g. story generation helpers).

## UI and UX text
- [ ] Confirm new languages appear in all language selectors (project create/edit, profile dialogue language, filters).
- [ ] Confirm labels are natural and consistent across forms.

## Validation and integration points
- [ ] Verify any allow-lists derived from language choices (e.g. pivot language validation) accept the new codes.
- [ ] Check any serialization/import-export paths preserve the new codes.

## Regression/testing pass
- [ ] Form rendering tests for dropdown values.
- [ ] Create/edit project flow with each new language as text language and glossing language.
- [ ] Any pipeline smoke tests that depend on language metadata.
