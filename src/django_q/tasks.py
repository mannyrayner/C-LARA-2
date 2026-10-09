from __future__ import annotations

import os
import threading
from importlib import import_module
from typing import Any, Callable


CONNECTION_CLEANUP_VERSION = 1
_slots_lock = threading.Lock()
_slots_key = None
_slots = None


def fallback_worker_limit() -> int:
    """Bound active fallback tasks per process, not across Gunicorn workers."""
    from django.conf import settings

    configured = getattr(settings, "Q_CLUSTER", {}) if settings.configured else {}
    try:
        return max(1, min(8, int(configured.get("workers", 2))))
    except (TypeError, ValueError, OverflowError):
        return 2


def _worker_slots():
    global _slots, _slots_key
    key = (os.getpid(), fallback_worker_limit())
    with _slots_lock:
        if key != _slots_key:
            _slots = threading.BoundedSemaphore(key[1])
            _slots_key = key
        return _slots


def _close_task_connections():
    from django.conf import settings
    from django.db import connections

    if settings.configured:
        # Django connections are thread-local. Request-finished cleanup does
        # not run for these threads; close_old_connections alone can retain
        # healthy persistent connections. Never call this in the sync branch.
        connections.close_all()


def _resolve_task_callable(func: Callable[..., Any] | str) -> Callable[..., Any]:
    """Resolve a Django-Q style dotted task path to a callable."""

    if callable(func):
        return func
    if not isinstance(func, str) or "." not in func:
        raise TypeError("async_task func must be a callable or dotted import path")
    module_name, callable_name = func.rsplit(".", 1)
    module = import_module(module_name)
    resolved = getattr(module, callable_name)
    if not callable(resolved):
        raise TypeError(f"async_task target {func!r} is not callable")
    return resolved


def async_task(
    func: Callable[..., Any] | str,
    *args: Any,
    hook: Callable[..., Any] | None = None,
    q_options: dict | None = None,
    **kwargs: Any,
):
    """Run a task asynchronously or synchronously based on ``q_options``.

    This minimal stub mimics the Django Q ``async_task`` signature so code can
    be developed and tested without the external dependency. When ``sync`` is
    truthy in ``q_options``, the task runs inline; otherwise it runs in a
    background thread. Active task bodies (including hooks and connection
    cleanup) share a process-local limit from Q_CLUSTER['workers'], capped at
    eight. Waiting threads are still in-memory and tasks are not durable.
    """

    q_opts = q_options or {}
    task_callable = _resolve_task_callable(func)
    if q_opts.get("sync"):
        result = task_callable(*args, **kwargs)
        if hook:
            hook(result)
        return result

    slots = _worker_slots()

    def _runner():
        # Acquire inside the new thread: nested fan-out must not block the
        # caller while it still owns a slot or a database transaction.
        with slots:
            try:
                result = task_callable(*args, **kwargs)
                if hook:
                    hook(result)
            finally:
                _close_task_connections()

    thread = threading.Thread(target=_runner, daemon=True)
    thread.start()
    return thread
