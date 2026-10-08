# Image-only copy review follow-up

8 October 2026. Apply on top of the Type/Speak/Suggest a description patch you just
tested. No new migration or dependency. Existing dictionaries/copies are not rewritten.

## Laptop

Stop runserver. Download `community_dictionary_image_copy_review.patch` to
`/home/github/`. The preceding patch may still be staged; you can apply this follow-up
on top without committing it first. Check for unrelated or unexpected changes:

```bash
cd /home/github/c-lara-2
git status --short
git diff --name-only
```

The unstaged diff should be empty. Then:

```bash
git apply --check ../community_dictionary_image_copy_review.patch &&
git apply --index ../community_dictionary_image_copy_review.patch &&
git diff --cached --check
cd platform_server
../.venv/Scripts/python.exe -E manage.py check &&
../.venv/Scripts/python.exe -E manage.py test community_dictionary &&
../.venv/Scripts/python.exe -E manage.py migrate --check
```

Expect **376 tests**, ending `OK`. Simulated timeout/failure messages inside tests
are intentional. No new migrations are required; the existing database should
already have migrations through 0017. Stop on unexpected failures.

```bash
../.venv/Scripts/python.exe -E manage.py runserver --insecure
```

## Try it

1. From the original Swedish dictionary, choose **Settings → Create an image-only
   copy**. Leave **Images to copy: Both**, give it a distinct name and confirm.
2. The new dictionary opens on **Awaiting review**. It should include both previously
   accepted images and Cathy's unreviewed additions. Duplicate derivatives count once.
3. If necessary, enable **Picture descriptions (OpenAI)** and saved spoken audio in
   this copy's Settings. The source dictionary's existing settings were inherited.
4. Open a picture, choose **Suggest a description → Continue → Prepare suggestion**
   with the usual permission. The picture remains pending during the preview.
5. **Yes — save and share** both accepts the picture and saves the description.
   **Next picture** should take you to another unprocessed picture, including pending
   ones. The remaining work stays in Awaiting review; completed sentences appear
   in Accepted.
6. Check that review states and content in the original dictionary did not change.

You are owner of the copy. Other members need an editor role to describe pending
images; ordinary members can describe accepted ones as before. Creating the copy
makes no API call. Describing pictures uses the usual consent, estimate and allowance.
Already-created test copies keep their old contents/statuses; hide an obsolete one
using Settings if necessary.

## Check in after acceptance

```bash
cd /home/github/c-lara-2
git diff --cached --stat
git diff --cached --check
git diff --name-only
git status --short
```

Expect only the current Community Dictionary code/tests/docs and global-state
records (plus the preceding patch if still staged), with no unstaged changes or
unrelated files. Then:

```bash
git commit -m "Improve image-only copying and review through picture descriptions" &&
git push origin main &&
git rev-parse HEAD &&
git status --short
```

## AWS after laptop acceptance

Use the AI-descriptions installation guide's AWS block for the combined release:
let active AI jobs finish; start with clean main; `umask 022`; activate `.venv` and
load `/etc/clara2.env`; stop Gunicorn, Django-Q and the project-understanding worker;
`git pull --ff-only origin main`; verify the laptop SHA; run `check`,
`migrate --check`, `collectstatic --noinput`; restart and inspect all three services.
No new migration, pip install, nginx restart or DEBUG change is required.

The full AWS commands are also in
`docs/howto/community-ai-descriptions-install.md` in the repository. Collectstatic
is needed if that preceding release has not yet been installed on AWS.
