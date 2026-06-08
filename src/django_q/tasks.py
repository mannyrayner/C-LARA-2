from __future__ import annotations

import threading
from importlib import import_module
from typing import Any, Callable


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
    background thread.
    """

    q_opts = q_options or {}
    task_callable = _resolve_task_callable(func)
    if q_opts.get("sync"):
        result = task_callable(*args, **kwargs)
        if hook:
            hook(result)
        return result

    def _runner():
        result = task_callable(*args, **kwargs)
        if hook:
            hook(result)

    thread = threading.Thread(target=_runner, daemon=True)
    thread.start()
    return thread
