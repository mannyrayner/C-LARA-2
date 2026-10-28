#!/bin/sh
# Installed root-owned at /opt/clara-deploy/services.sh. Fixed service set only.
set -eu
case "${1:-}" in
  start|stop)
    exec systemctl "$1" gunicorn-clara2 djangoq-clara2 project-understanding-worker
    ;;
  running)
    for unit in gunicorn-clara2 djangoq-clara2 project-understanding-worker; do
      test "$(systemctl is-active "$unit")" = active
    done
    ;;
  stopped)
    for unit in gunicorn-clara2 djangoq-clara2 project-understanding-worker; do
      state=$(systemctl is-active "$unit" || true)
      case "$state" in inactive|failed) ;; *) exit 1 ;; esac
    done
    ;;
  *) exit 2 ;;
esac
