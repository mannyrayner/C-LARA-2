import json
import os
from pathlib import Path
import tempfile
import threading
import subprocess
from unittest.mock import patch

from django.core.management import call_command
from django.core.management.base import CommandError
from django.http import HttpResponse, StreamingHttpResponse
from django.test import RequestFactory, TestCase
from core import deployment_activity as activity
from community_dictionary import deployment_health


class DeploymentTests(TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.env = patch.dict(os.environ, {'CLARA_DEPLOY_ACTIVITY_DIR':str(self.root)})
        self.env.start()
        self.addCleanup(self.env.stop)
        self.request = RequestFactory().get('/community-dictionaries/')

    def leases(self):
        return list(self.root.glob('*.lease'))

    def test_gate_blocks_both_apps_and_all_methods(self):
        (self.root / 'maintenance').touch()
        called = []
        middleware = deployment_health.DeploymentMiddleware(lambda r: called.append(r))
        for path in ('/', '/community-dictionaries/', '/accounts/login/'):
            response = middleware(RequestFactory().post(path))
            self.assertEqual(response.status_code, 503)
            self.assertEqual(response['Retry-After'], '30')
        self.assertEqual(called, [])
        self.assertEqual(self.leases(), [])

    def test_request_lease_is_present_only_while_running(self):
        def view(request):
            self.assertEqual(len(self.leases()), 1)
            return HttpResponse('ok')
        deployment_health.DeploymentMiddleware(view)(self.request)
        self.assertEqual(self.leases(), [])

    def test_exception_releases_request(self):
        def view(request):
            raise ValueError('test')
        with self.assertRaises(ValueError):
            deployment_health.DeploymentMiddleware(view)(self.request)
        self.assertEqual(self.leases(), [])

    def test_streaming_keeps_lease_until_response_closed(self):
        response = deployment_health.DeploymentMiddleware(lambda r: StreamingHttpResponse([b'a']))(self.request)
        self.assertEqual(len(self.leases()), 1)
        response.close()
        self.assertEqual(self.leases(), [])

    def test_gate_race_after_lease_creation_is_rejected(self):
        with patch.object(activity, 'paused', side_effect=[False, True]):
            with self.assertRaises(activity.Maintenance):
                activity.acquire('request')
        self.assertEqual(self.leases(), [])

    def test_disabled_integration_leaves_existing_behaviour_alone(self):
        with patch.dict(os.environ, {'CLARA_DEPLOY_ACTIVITY_DIR':''}):
            (self.root / 'maintenance').touch()
            response = deployment_health.DeploymentMiddleware(lambda r: HttpResponse('normal'))(self.request)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(self.client.get(deployment_health.HEALTH_PATH).status_code, 404)

    def test_health_remains_available_during_maintenance_and_has_no_content(self):
        (self.root / 'maintenance').touch()
        with patch.object(deployment_health, 'RELEASE', 'a' * 40):
            response = self.client.get(deployment_health.HEALTH_PATH)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {'ready':True, 'release':'a' * 40, 'maintenance':True})
        self.assertIn('no-store', response['Cache-Control'])

    def test_database_failure_is_not_disclosed(self):
        with patch.object(deployment_health.connection, 'cursor', side_effect=RuntimeError('private password')):
            response = deployment_health.health(RequestFactory().get(deployment_health.HEALTH_PATH))
        self.assertEqual(response.status_code, 503)
        self.assertNotIn('private password', response.content.decode())

    def test_background_lease_covers_waiting_and_running_work(self):
        from django_q import tasks
        entered, finish, second_entered = threading.Event(), threading.Event(), threading.Event()
        def task():
            entered.set()
            finish.wait(5)
        with patch.object(tasks, '_close_task_connections'), patch.object(tasks, '_worker_slots', return_value=threading.BoundedSemaphore(1)):
            thread = tasks.async_task(task)
            self.assertTrue(entered.wait(3))
            self.assertEqual(len(self.leases()), 1)
            (self.root / 'maintenance').touch()
            second = tasks.async_task(lambda: second_entered.set())
            self.assertEqual(len(self.leases()), 2)
            self.assertFalse(second_entered.is_set())
            finish.set()
            thread.join(3)
            second.join(3)
            self.assertFalse(thread.is_alive())
            self.assertFalse(second.is_alive())
        self.assertEqual(self.leases(), [])

    def test_thread_start_failure_releases_lease(self):
        from django_q import tasks
        with patch.object(tasks.threading.Thread, 'start', side_effect=RuntimeError('test')):
            with self.assertRaises(RuntimeError):
                tasks.async_task(lambda: None)
        self.assertEqual(self.leases(), [])

    def test_preflight_rejects_wrong_activity_directory(self):
        with self.assertRaises(CommandError):
            call_command('community_deployment_check', activity_dir=str(self.root / 'other'), backend='sqlite')

    def test_preflight_rejects_unexpected_queue_without_switching_it(self):
        with self.settings(USE_REAL_DJANGO_Q=True), self.assertRaises(CommandError):
            call_command('community_deployment_check', activity_dir=str(self.root), backend='sqlite')
        self.assertEqual(self.leases(), [])

    def test_preflight_refuses_pending_migrations(self):
        with patch('community_dictionary.management.commands.community_deployment_check.MigrationExecutor') as executor:
            executor.return_value.migration_plan.return_value = [('pending', False)]
            with self.assertRaisesMessage(CommandError, 'Pending migrations'):
                call_command('community_deployment_check', activity_dir=str(self.root), backend='sqlite')
        self.assertEqual(self.leases(), [])

    def test_capture_release_trusts_only_configured_checkout_and_freezes_identity(self):
        with patch.object(deployment_health, 'RELEASE', ''):
            with patch.object(deployment_health.subprocess, 'run', return_value=subprocess.CompletedProcess([], 0, 'a' * 40 + '\n')) as git:
                deployment_health.capture_release()
                args = git.call_args.args[0]
                self.assertIn('safe.directory=' + str(deployment_health.settings.BASE_DIR.parent.resolve()), args)
                self.assertEqual(deployment_health.RELEASE, 'a' * 40)
                self.client.get(deployment_health.HEALTH_PATH)
                git.assert_called_once()

    def test_worker_does_not_claim_requests_while_maintenance_is_active(self):
        (self.root / 'maintenance').touch()
        with patch('projects.management.commands.process_project_understanding_queue._claim_next_project_understanding_request') as claim:
            call_command('process_project_understanding_queue', '--once')
        claim.assert_not_called()
        self.assertEqual(self.leases(), [])
