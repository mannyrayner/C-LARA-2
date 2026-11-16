#!/bin/sh
# Root-owned helper; app commands always run as the unprivileged staging user.
set -eu
case "$*" in
  'check'|'makemigrations --check --dry-run'|'collectstatic --noinput'|'community_deployment_check --activity-dir /var/lib/clara-staging-activity --backend postgresql') ;;
  *) exit 2 ;;
esac
exec /usr/bin/systemd-run --quiet --wait --pipe --collect \
  --property=User=clara-staging --property=Group=www-data \
  --property=RuntimeMaxSec=90 --property=TimeoutStopSec=15 \
  --property=WorkingDirectory=/srv/C-LARA-2-staging/platform_server \
  --property=EnvironmentFile=/etc/clara-staging.env \
  /srv/C-LARA-2-staging/.venv/bin/python manage.py "$@"
