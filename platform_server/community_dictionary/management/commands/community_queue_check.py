"""Exercise fallback task connections without touching application data or AI."""
import threading
import time

from django.core.management.base import BaseCommand, CommandError
from django.db import connections


class Command(BaseCommand):
    help = "Read-only check of the fallback queue's concurrency and DB cleanup."

    def add_arguments(self, parser):
        parser.add_argument('--tasks', type=int, default=20)

    def handle(self, *args, **options):
        import django_q.tasks as queue

        if not getattr(queue, 'CONNECTION_CLEANUP_VERSION', 0):
            raise CommandError('This check requires the patched local fallback queue.')
        count = options['tasks']
        if not 1 <= count <= 40:
            raise CommandError('--tasks must be between 1 and 40.')
        if connections['default'].vendor == 'sqlite' and connections['default'].is_in_memory_db():
            raise CommandError('Use a file-backed SQLite or PostgreSQL database; Django deliberately keeps in-memory SQLite connections open.')
        self.stdout.write(f'Queue implementation: {queue.__file__}')
        self.stdout.write(f'Connection cleanup version: {queue.CONNECTION_CLEANUP_VERSION}')
        limit = queue.fallback_worker_limit()
        self.stdout.write(f'Active task limit in this process: {limit}')
        lock = threading.Lock()
        wrappers, errors = [], []
        active = peak = finished = 0

        def probe():
            nonlocal active, peak, finished
            with lock:
                active += 1
                peak = max(peak, active)
            try:
                db = connections['default']
                with lock:
                    wrappers.append(db)
                with db.cursor() as cursor:
                    cursor.execute('SELECT 1')
                    if cursor.fetchone() != (1,):
                        raise RuntimeError('Unexpected SELECT result')
                # Give concurrent tasks time to overlap. No provider calls or
                # application reads/writes; retained wrappers detect GC leaks.
                time.sleep(0.02)
                with lock:
                    finished += 1
            except Exception as exc:
                with lock:
                    errors.append(type(exc).__name__)
            finally:
                with lock:
                    active -= 1

        threads = [queue.async_task(probe) for _ in range(count)]
        deadline = time.monotonic() + 30
        for thread in threads:
            thread.join(max(0, deadline - time.monotonic()))
        if any(thread.is_alive() for thread in threads):
            raise CommandError('Probe exceeded 30 seconds. Do not resume AI jobs yet.')
        open_count = sum(db.connection is not None for db in wrappers)
        self.stdout.write(f'Completed SELECT probes: {finished}/{count}')
        self.stdout.write(f'Peak simultaneous probe bodies: {peak} (limit {limit})')
        self.stdout.write(f'Task connections still open after completion: {open_count}')
        if errors or finished != count or peak > limit or open_count:
            raise CommandError(f'Queue check failed; error types: {", ".join(errors) or "none"}.')
        self.stdout.write(self.style.SUCCESS('Queue check passed. No app data changed and no AI requests sent.'))
