# Image contribution ladder

19 October 2026

Patch: `community_image_ladder.patch`

Base: `8053bd128a22f87f2f75cbd5e30fad1d3890b1e6`
(`Enable English carrier extraction for expression audio`). Apply this incremental
patch after the accepted English carrier update.

## What Cathy can try

Open a shared dictionary's **People** page. **Images contributed** appears before
the membership controls. In French, look under **Personnes** for **Images
apportées**. The table shows rank, contributor and image count. Equal totals share
a rank, with names ordered consistently within a tie. It works without JavaScript.

The total spans the viewer's currently accessible shared dictionaries, excluding
hidden and archived dictionaries and personal collections. Different memberships
can therefore produce different totals. The ladder remains inside member-only
People; visitor browsing does not gain contributor names or a new ranking page.

Only accepted human-uploaded images on live entries count. A picture need not be
the entry's selected image. AI-generated images, dictionary styles, proposals,
rejected/removed/withdrawn media and withdrawn dependencies do not count. Existing
image attribution is respected, including contributions explicitly credited to
someone by an uploader acting on their behalf.

An explicit copy family counts once for its original contributor, even when
language porting or picture descriptions reuse the image. An accepted accessible
copy can count when the original dictionary is hidden or inaccessible: only the
shared copy supplies eligibility. Withdrawal still removes its credit. Separately
uploaded files without recorded copy provenance remain separate contributions;
the app does not compare image pixels or guess identity from filenames.

The table has wrapping names and narrow numeric columns for mobile screens. Its
English and French messages and compiled French catalog are included. This patch
adds CSS and changes its cache version to 15, so **AWS needs collectstatic**.
There is no new migration, dependency, environment variable or paid operation.

## Laptop installation

Stop the development server. Put the extracted patch next to the repository:

```bash
cd /home/github/c-lara-2
git status --short
git log -1 --oneline
git apply --check ../community_image_ladder.patch &&
git apply --index ../community_image_ladder.patch &&
git diff --cached --check

cd platform_server
../.venv/Scripts/python.exe -E manage.py check &&
../.venv/Scripts/python.exe -E manage.py makemigrations --check --dry-run community_dictionary &&
../.venv/Scripts/python.exe -E manage.py test community_dictionary &&
../.venv/Scripts/python.exe -E manage.py migrate --check
```

Expected: **701 tests, OK**, with no migration changes. If the patch check
fails, stop and preserve unrelated work. GNU gettext is not required to install
the included compiled French catalog. Restart as usual:

```bash
../.venv/Scripts/python.exe -E manage.py runserver 127.0.0.1:8000 --insecure
```

Open **People**, check the totals against a few known human pictures, and switch
between English and French. Compare original and language-ported copies: reuse
must not increase the total. Images available only in hidden dictionaries and AI
images should be absent. Try a narrow/mobile window. Existing invitations,
membership controls and partnerships remain on the same page.

Once accepted, review and commit the patch:

```bash
cd /home/github/c-lara-2
git diff --cached --check
git diff --cached --stat
git commit -m "Add image contribution ladder under People" &&
git push origin main
git rev-parse HEAD
```

Use the normal branch/review process if your checkout is not on `main`.

## AWS installation

Let current AI jobs finish. Keep normal backups. This update does not rewrite
dictionary content, media, attribution or membership. Start with a clean checkout:

```bash
sudo -iu ssm-user
cd /srv/C-LARA-2
umask 022
git status --short
git rev-parse HEAD
```

Define the established management helper in this shell:

```bash
clara_manage() {
  sudo systemd-run --quiet --wait --pipe --collect \
    --property=User=ubuntu \
    --property=Group=www-data \
    --property=WorkingDirectory=/srv/C-LARA-2/platform_server \
    --property=EnvironmentFile=/etc/clara2.env \
    /srv/C-LARA-2/.venv/bin/python manage.py "$@"
}

sudo systemctl stop gunicorn-clara2 djangoq-clara2 project-understanding-worker &&
git pull --ff-only &&
clara_manage check &&
clara_manage migrate --check &&
clara_manage collectstatic --noinput &&
sudo systemctl start gunicorn-clara2 djangoq-clara2 project-understanding-worker

sudo systemctl status --no-pager gunicorn-clara2 djangoq-clara2 project-understanding-worker
git rev-parse HEAD
```

Stop on any error and keep the output. Confirm all three services are running and
the deployed SHA matches the accepted laptop commit. Reload People in Chrome or
Firefox on the laptop and phone. The new CSS URL ends in `app.css?v=15`.

## Verification and trial context

The full Community Dictionaries suite passes **701 tests**, including 16
new ladder regressions covering accepted human media, copy and language-port
families, original delegated attribution, hidden/private/member access,
withdrawal/restoration, AI/style ancestry, malformed copy chains, deterministic
ties and bounded database queries. Actual member People rendering/access and
English/French labels are covered. Template, translation, migration and system
checks also pass. Test data and providers are local fixtures; no paid request or
production data change is needed.

Manny reports the preceding English carrier increment worked, without a new
quantitative English listening result. He and Cathy report that the sample AWS
entry renders normally in mobile Chrome and Firefox; an earlier issue in an
AdBlock setup remains undiagnosed. Safari and full mobile workflow acceptance are
still unconfirmed. The agreed direction is workflow tidying, independent quality
ratings with inter-rater figures, then an exploratory communal dictionary pilot.
A Zoom is tentatively planned for Monday 26 October; an Alliance Française visit
is being considered, with no appointment or group participation confirmed.

This ladder is Cathy's proposed first contribution-recognition feature. Her
acceptance of its presentation and any effect on participation remain to be
tested. Counts measure contributions, not learning outcomes or teaching quality.
