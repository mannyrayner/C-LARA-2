"""Production incident regression: thread connections must not await cyclic GC."""
import os
import subprocess
import sys
import threading
from unittest.mock import patch

from django.conf import settings
from django.core.management import CommandError
from django.test import SimpleTestCase, override_settings
from django.urls import path

from django_q import tasks


def broken_view(request):
    raise RuntimeError('queue-test-private-error')


urlpatterns = [path('queue-test-error/', broken_view)]


@override_settings(Q_CLUSTER={'workers': 2})
class BackgroundQueueTests(SimpleTestCase):
    def child_python(self, source):
        env = os.environ.copy()
        env.pop('DJANGO_SETTINGS_MODULE', None)
        paths = [str(settings.ROOT_DIR / 'src'), str(settings.BASE_DIR), env.get('PYTHONPATH', '')]
        env['PYTHONPATH'] = os.pathsep.join(paths)
        result = subprocess.run([sys.executable, '-c', source], env=env,
                                capture_output=True, text=True, timeout=40)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return result.stdout

    def test_task_and_hook_connections_close_on_success_and_failure(self):
        output = self.child_python('''
import gc, tempfile, threading
from pathlib import Path
from django.conf import settings
with tempfile.TemporaryDirectory() as root:
    settings.configure(DATABASES={name: {'ENGINE': 'django.db.backends.sqlite3',
        'NAME': str(Path(root) / (name + '.sqlite3')), 'CONN_MAX_AGE': 600}
        for name in ['default', 'other']}, Q_CLUSTER={'workers': 2})
    from django.db import connections, transaction
    from django_q.tasks import async_task
    gc.disable()
    wrappers, raw, failures = [], [], []
    threading.excepthook = lambda args: failures.append(args.exc_type)
    def query(alias='default'):
        db = connections[alias]
        with db.cursor() as cursor:
            cursor.execute('SELECT 1')
            assert cursor.fetchone() == (1,)
        wrappers.append(db)
        raw.append(db.connection)
        return 'ok'
    def fail():
        query()
        raise ValueError('expected task failure')
    def hook(value):
        assert value == 'ok'
        query('other')
    def bad_hook(value):
        hook(value)
        raise RuntimeError('expected hook failure')
    threads = [async_task(query, hook=hook), async_task(fail),
               async_task(query, hook=bad_hook)]
    for thread in threads:
        thread.join(10)
        assert not thread.is_alive()
    assert len(wrappers) == 5
    assert all(db.connection is None for db in wrappers), 'Leaked thread connection'
    assert sorted(kind.__name__ for kind in failures) == ['RuntimeError', 'ValueError']
    for connection in raw:
        import sqlite3
        try:
            connection.execute('SELECT 1')
        except sqlite3.ProgrammingError:
            pass
        else:
            raise AssertionError('Underlying SQLite handle was not closed')
    # Synchronous work shares the caller's transaction; never close it.
    with transaction.atomic():
        caller = connections['default']
        before = caller.connection
        assert async_task(query, hook=hook, q_options={'sync': True}) == 'ok'
        assert caller.connection is before
        assert caller.in_atomic_block
        with caller.cursor() as cursor:
            cursor.execute('SELECT 1')
    connections.close_all()
    gc.enable()
print('File-backed connections and caller transaction verified')
''')
        self.assertIn('caller transaction verified', output)

    def test_concurrency_slot_is_held_until_cleanup_finishes(self):
        release = threading.Event()
        two_cleaning = threading.Event()
        lock = threading.Lock()
        started = []
        cleaning = 0

        def body():
            with lock:
                started.append(threading.get_ident())

        def cleanup():
            nonlocal cleaning
            with lock:
                cleaning += 1
                if cleaning == 2:
                    two_cleaning.set()
            release.wait(5)

        with patch.object(tasks, '_close_task_connections', side_effect=cleanup):
            threads = [tasks.async_task(body) for _ in range(20)]
            try:
                self.assertTrue(two_cleaning.wait(3))
                self.assertEqual(len(started), 2)
            finally:
                release.set()
                for thread in threads:
                    thread.join(5)
            self.assertEqual(len(started), 20)
            self.assertTrue(all(not t.is_alive() for t in threads))

    @override_settings(Q_CLUSTER={'workers': 1})
    def test_nested_fan_out_can_enqueue_without_blocking_parent(self):
        children = []
        completed = threading.Event()
        parent = tasks.async_task(lambda: children.append(tasks.async_task(completed.set)))
        parent.join(3)
        self.assertFalse(parent.is_alive())
        self.assertTrue(completed.wait(3))
        children[0].join(3)

    def test_invalid_limits_are_safe_and_large_limits_are_capped(self):
        for configured, expected in [(None, 2), ('bad', 2), (0, 1), (-1, 1), (100, 8), ('3', 3)]:
            with self.subTest(configured=configured), override_settings(Q_CLUSTER={'workers': configured}):
                self.assertEqual(tasks.fallback_worker_limit(), expected)

    def test_fallback_can_run_without_configured_django(self):
        self.child_python('''
from django_q.tasks import async_task
results = []
thread = async_task(lambda: results.append('done'))
thread.join(3)
assert results == ['done']
assert async_task('builtins.len', [1, 2], q_options={'sync': True}) == 2
''')

    def test_server_probe_passes_with_real_file_connections(self):
        self.child_python('''
import tempfile
from pathlib import Path
from django.conf import settings
with tempfile.TemporaryDirectory() as root:
    settings.configure(DATABASES={'default': {'ENGINE': 'django.db.backends.sqlite3',
        'NAME': str(Path(root) / 'probe.sqlite3')}}, Q_CLUSTER={'workers': 2})
    from community_dictionary.management.commands.community_queue_check import Command
    Command().handle(tasks=20)
''')

    def test_probe_rejects_unpatched_or_external_queue(self):
        from community_dictionary.management.commands.community_queue_check import Command
        with patch.object(tasks, 'CONNECTION_CLEANUP_VERSION', 0):
            with self.assertRaisesMessage(CommandError, 'patched local fallback'):
                Command().handle(tasks=20)


@override_settings(DEBUG=False, ROOT_URLCONF=__name__)
class RequestErrorLoggingTests(SimpleTestCase):
    def test_production_500_logs_traceback_without_exposing_it(self):
        import logging
        from io import StringIO
        logger = logging.getLogger('django.request')
        handlers = [h for h in logger.handlers if isinstance(h, logging.StreamHandler)]
        self.assertTrue(handlers)
        output = StringIO()
        handler = handlers[0]
        old_stream = handler.setStream(output)
        self.client.raise_request_exception = False
        try:
            response = self.client.get('/queue-test-error/')
        finally:
            handler.setStream(old_stream)
        self.assertEqual(response.status_code, 500)
        self.assertNotIn(b'queue-test-private-error', response.content)
        self.assertIn('RuntimeError: queue-test-private-error', output.getvalue())
        self.assertIn('Traceback', output.getvalue())
