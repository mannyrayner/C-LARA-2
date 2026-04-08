from __future__ import annotations

import threading
from typing import Any, Callable


def async_task(func: Callable[..., Any], *args: Any, hook: Callable[..., Any] | None = None, q_options: dict | None = None, **kwargs: Any):
    """Run a task asynchronously or synchronously based on ``q_options``.

    This minimal stub mimics the Django Q ``async_task`` signature so code can
    be developed and tested without the external dependency. When ``sync`` is
    truthy in ``q_options``, the task runs inline; otherwise it runs in a
    background thread.
    """

    q_opts = q_options or {}
    if q_opts.get("sync"):
        result = func(*args, **kwargs)
        if hook:
            hook(result)
        return result

    def _runner():
        result = func(*args, **kwargs)
        if hook:
            hook(result)

    thread = threading.Thread(target=_runner, daemon=True)
    thread.start()
    return thread
