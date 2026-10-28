"""Optional file leases for draining this installation before a code release.

Disabled unless CLARA_DEPLOY_ACTIVITY_DIR is configured. No content or credentials
are recorded. A crashed process leaves its lease behind: fail closed, never guess
from age that a paid task is safe to interrupt.
"""
from contextlib import contextmanager
import json
import os
from pathlib import Path
import uuid

VERSION = 1


def directory():
    value = os.environ.get('CLARA_DEPLOY_ACTIVITY_DIR', '')
    return Path(value) if value else None


def paused():
    root = directory()
    return bool(root and (root / 'maintenance').exists())


def acquire(kind, respect_gate=True):
    root = directory()
    if root is None:
        return None
    if respect_gate and paused():
        raise Maintenance()
    # Bootstrap creates this directory with the intended host permissions.
    path = root / (uuid.uuid4().hex + '.lease')
    with path.open('x', encoding='utf-8') as stream:
        json.dump({'pid': os.getpid(), 'kind': kind}, stream)
    if respect_gate and paused():
        path.unlink()
        raise Maintenance()
    return path


def release(path):
    if path is not None:
        path.unlink(missing_ok=True)


class Maintenance(Exception):
    pass


@contextmanager
def activity(kind, respect_gate=True):
    lease = acquire(kind, respect_gate)
    try:
        yield
    finally:
        release(lease)
