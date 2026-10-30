# Dictionary Tools

The dictionary owner now has a **Tools** tab beside **Settings**. Its French
label is **Outils** and its Slovak label is **Nástroje**.

Tools groups operations on dictionary content:

- Add missing sentences, including vocabulary and audio through the existing workflow.
- Create or update language versions and their vocabulary.
- Regenerate AI expression audio.
- Create an image-only copy.

Settings keeps the dictionary name, visibility, discoverability, public browsing,
workflow suggestions, description allowance, language/AI configuration and image style.
The workflow-suggestions explanation points owners to Tools for manual access.

Opening Tools does not start processing. Each operation keeps its existing preview,
cost approval, permissions and review choices. Existing task URLs and saved links
continue to work. The four task start pages link back to Tools, and the tab stays
highlighted during their workflows. Members, editors and visitors do not gain owner
permissions. Personal collections and withdrawn participation cannot use Tools.

## Deployment trial

This is a code/template/catalogue change: no migration, dependency, controller or
environment update. The compiled French and Slovak catalogues are included.
Use the existing supervised laptop workflow, then inspect these points as an owner:

1. Tools appears beside Settings and contains the four operations above.
2. Settings contains configuration rather than those operations.
3. Open each operation and use Back to Tools; no processing is needed for this check.
4. Optionally choose French or Slovak to check the new tab's label.

After laptop acceptance, use the existing Accept laptop and deploy AWS workflow to
install the same commit. A new workflow run is needed for a new release request;
rerunning an old run uses that run's old control-repository commit.
