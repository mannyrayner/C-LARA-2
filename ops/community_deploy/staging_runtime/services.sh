#!/bin/sh
# Root-owned, staging-only copy; never called with application-supplied unit names.
set -eu
case "${1:-}" in
  start)
    /opt/clara-staging-guard/bin/python /opt/clara-staging-deploy/staging_fault.py --consume
    exec systemctl start gunicorn-clara-staging understanding-clara-staging
    ;;
  stop)
    exec systemctl "$1" gunicorn-clara-staging understanding-clara-staging
    ;;
  running)
    for unit in gunicorn-clara-staging understanding-clara-staging; do
      test "$(systemctl is-active "$unit")" = active
    done
    ;;
  stopped)
    for unit in gunicorn-clara-staging understanding-clara-staging; do
      state=$(systemctl is-active "$unit" || true)
      case "$state" in inactive|failed) ;; *) exit 1 ;; esac
    done
    ;;
  *) exit 2 ;;
esac
