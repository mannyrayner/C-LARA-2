# Common server admin tasks (C-LARA-2 on AWS)

This page is a practical runbook for day-to-day operations on the production host.

Assumptions:
- Repo path: `/srv/C-LARA-2`
- App env file: `/etc/clara2.env`
- Services: `gunicorn-clara2`, `djangoq-clara2`, `nginx`

---

## 1) Pull latest code and restart services

Use this after new changes are checked in.

```bash
cd /srv/C-LARA-2
git pull --ff-only
. .venv/bin/activate
python -m pip install -r requirements.txt
cd platform_server
set -a && . /etc/clara2.env && set +a
python manage.py check
python manage.py migrate
python manage.py collectstatic --noinput
sudo systemctl restart gunicorn-clara2 djangoq-clara2
sudo systemctl reload nginx
```

Quick verification:

```bash
sudo systemctl status --no-pager gunicorn-clara2 djangoq-clara2 nginx
curl -I https://c-lara-2.c-lara.org
```

---

## 2) Check service health and logs

Status:

```bash
sudo systemctl status --no-pager gunicorn-clara2 djangoq-clara2 nginx
```

Live logs:

```bash
sudo journalctl -u gunicorn-clara2 -f
sudo journalctl -u djangoq-clara2 -f
sudo tail -f /var/log/nginx/access.log /var/log/nginx/error.log
```

Recent startup errors:

```bash
sudo journalctl -u gunicorn-clara2 -n 120 --no-pager
sudo journalctl -u djangoq-clara2 -n 120 --no-pager
```

---

## 3) Edit environment variables safely

When changing API keys, DB settings, or feature flags:

```bash
sudoedit /etc/clara2.env
```

Then reload app services:

```bash
sudo systemctl restart gunicorn-clara2 djangoq-clara2
```

Optional config check:

```bash
cd /srv/C-LARA-2/platform_server
set -a && . /etc/clara2.env && set +a
python manage.py check
```

---

## 4) Dependency updates (when runtime import errors appear)

Typical symptom: `No module named ...` in compile/worker logs.

```bash
cd /srv/C-LARA-2
. .venv/bin/activate
python -m pip install -r requirements.txt
sudo systemctl restart gunicorn-clara2 djangoq-clara2
```

Sanity check for installed modules:

```bash
python -c "import openai, indic_transliteration, pypinyin; print('imports ok')"
```

---

## 5) Permissions reset for media/static (common fix)

Use this if project creation/compile fails with `PermissionError` under `platform_server/media`.

```bash
sudo install -d -m 2775 -o ubuntu -g www-data /srv/C-LARA-2/platform_server/media
sudo chown -R ubuntu:www-data /srv/C-LARA-2/platform_server/media
sudo find /srv/C-LARA-2/platform_server/media -type d -exec chmod 2775 {} \;
sudo find /srv/C-LARA-2/platform_server/media -type f -exec chmod 664 {} \;
```

---

## 6) TLS certificate checks (Let's Encrypt)

```bash
sudo systemctl status --no-pager certbot.timer
sudo certbot renew --dry-run
```

---

## 7) Basic smoke test after any deploy

1. Open `https://c-lara-2.c-lara.org`
2. Log in and open an existing project
3. Create or edit a project
4. Run compile
5. Confirm output opens in viewer/editor

If anything fails, capture:
- exact timestamp,
- user/project id,
- `gunicorn` + `djangoq` log snippets.

---

## 8) Fast rollback to previous commit

If a fresh deploy causes breakage and you need to stabilize quickly:

```bash
cd /srv/C-LARA-2
git log --oneline -n 10
git checkout <last-known-good-commit>
. .venv/bin/activate
python -m pip install -r requirements.txt
cd platform_server
set -a && . /etc/clara2.env && set +a
python manage.py check
sudo systemctl restart gunicorn-clara2 djangoq-clara2
sudo systemctl reload nginx
```

Then open the app and run the smoke test again.

---

## 9) Handy one-liners

Check current branch and commit:

```bash
cd /srv/C-LARA-2
git rev-parse --abbrev-ref HEAD
git rev-parse HEAD
```

Check socket permissions (nginx ↔ gunicorn):

```bash
sudo ls -ld /run/gunicorn-clara2
sudo ls -l /run/gunicorn-clara2/gunicorn.sock
```

