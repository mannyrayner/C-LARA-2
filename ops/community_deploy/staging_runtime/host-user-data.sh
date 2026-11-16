#!/bin/bash
# One-time OS preparation only. No application, database or production data is copied.
set -euo pipefail
trap 'systemctl poweroff --no-block' EXIT
install -d -m 0700 /var/lib/clara-staging-bootstrap
cat >/etc/systemd/system/clara-bootstrap-deadline.service <<'EOF'
[Service]
Type=oneshot
ExecStart=/usr/bin/systemctl poweroff --no-block
EOF
cat >/etc/systemd/system/clara-bootstrap-deadline.timer <<'EOF'
[Unit]
Description=Bound manual staging bootstrap sessions
[Timer]
OnBootSec=30min
Unit=clara-bootstrap-deadline.service
[Install]
WantedBy=timers.target
EOF
systemctl daemon-reload
systemctl enable --now clara-bootstrap-deadline.timer
export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y ca-certificates curl gnupg git unzip python3-venv python3-dev build-essential libpq-dev nginx apache2-utils certbot awscli
install -d -m 0755 /usr/share/postgresql-common/pgdg
curl --fail --silent --show-error https://www.postgresql.org/media/keys/ACCC4CF8.asc -o /usr/share/postgresql-common/pgdg/apt.postgresql.org.asc
. /etc/os-release
test "$VERSION_CODENAME" = noble
echo "deb [signed-by=/usr/share/postgresql-common/pgdg/apt.postgresql.org.asc] https://apt.postgresql.org/pub/repos/apt ${VERSION_CODENAME}-pgdg main" >/etc/apt/sources.list.d/pgdg.list
apt-get update
apt-get install -y postgresql-18
systemctl enable --now postgresql
systemctl start snap.amazon-ssm-agent.amazon-ssm-agent.service || systemctl start amazon-ssm-agent.service
touch /var/lib/clara-staging-bootstrap/os-ready
# The initial boot stops here. Subsequent manual setup boots retain the 30-minute guard.
