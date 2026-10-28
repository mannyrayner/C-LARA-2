"""Real Git and HTTP/supervisor integration in disposable local directories."""
from contextlib import redirect_stdout
from datetime import datetime, timezone
import importlib.util
import io
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
import runner
import cloud

APP = '''import json, os, subprocess, sys
from pathlib import Path
from http.server import BaseHTTPRequestHandler, HTTPServer
if sys.argv[1] == 'runserver':
    commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip()
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if Path('../bad.txt').exists():
                self.send_response(503); self.end_headers(); return
            self.send_response(200); self.end_headers()
            self.wfile.write(json.dumps({'ready':True, 'release':commit}).encode())
        def log_message(self, *a): pass
    host, port = sys.argv[2].split(':')
    HTTPServer((host, int(port)), Handler).serve_forever()
elif sys.argv[1] == 'collectstatic' and Path('../static-bad.txt').exists():
    print('private test diagnostic must not appear in receipt', file=sys.stderr)
    sys.exit(3)
'''


class GitDeploymentTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.origin = self.root / 'origin'
        self.repo = self.root / 'app'
        self.origin.mkdir()
        self.git_at(self.origin, 'init', '-b', 'main')
        self.git_at(self.origin, 'config', 'user.email', 'test@example.invalid')
        self.git_at(self.origin, 'config', 'user.name', 'Test')
        (self.origin / 'platform_server').mkdir()
        (self.origin / 'platform_server/manage.py').write_text(APP)
        self.git_at(self.origin, 'add', '.')
        self.git_at(self.origin, 'commit', '-m', 'base')
        self.base = self.git_at(self.origin, 'rev-parse', 'HEAD')
        self.git_at(self.root, 'clone', str(self.origin), str(self.repo))
        self.git_at(self.repo, 'config', 'user.email', 'test@example.invalid')
        self.git_at(self.repo, 'config', 'user.name', 'Test')
        self.activity = self.root / 'activity'
        self.activity.mkdir()
        with socket.socket() as s:
            s.bind(('127.0.0.1', 0))
            port = s.getsockname()[1]
        self.config = self.root / 'host.json'
        self.config.write_text(json.dumps({'target':'laptop', 'repo':str(self.repo),
            'state':str(self.root / 'state'), 'activity_dir':str(self.activity),
            'manage':[sys.executable, 'manage.py'], 'static_manage':[sys.executable, 'manage.py'],
            'address':f'127.0.0.1:{port}', 'timeout_seconds':5,
            'health_url':f'http://127.0.0.1:{port}/health/'}))
        self.receipt = self.root / 'receipt.json'
        self.controller = runner.Controller(self.config)
        self.source = patch.object(runner, 'SOURCE', str(self.origin))
        self.source.start()

    def tearDown(self):
        self.source.stop()
        self.controller.stop_server()
        self.temp.cleanup()

    def git_at(self, path, *args):
        return subprocess.check_output(['git', *args], cwd=path, stderr=subprocess.DEVNULL, text=True).strip()

    def change(self, name='feature.txt'):
        path = self.origin / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('new\n')
        self.git_at(self.origin, 'add', '.')
        self.git_at(self.origin, 'commit', '-m', 'candidate')
        return self.git_at(self.origin, 'rev-parse', 'HEAD')

    def install(self, commit, expected=None):
        return self.controller.install(commit, expected or self.base, self.receipt)

    def test_exact_release_is_installed_started_and_recorded(self):
        target = self.change()
        result = self.install(target)
        self.assertEqual(result['status'], 'installed')
        self.assertEqual(self.controller.head(), target)
        self.assertEqual(json.loads(self.receipt.read_text())['commit'], target)
        self.assertFalse((self.activity / 'maintenance').exists())
        self.controller.ready(target)

    def test_existing_managed_server_is_restarted(self):
        self.assertEqual(self.install(self.base)['status'], 'installed')
        old = self.controller.local_session()
        self.assertEqual(self.install(self.change())['status'], 'installed')
        self.assertTrue((old / 'exited').exists())
        self.assertNotEqual(old, self.controller.local_session())

    def test_bad_health_recovers_previous_code_and_server(self):
        result = self.install(self.change('bad.txt'))
        self.assertEqual(result['status'], 'recovered_previous_release')
        self.assertEqual(self.controller.head(), self.base)
        self.controller.ready(self.base)
        self.assertFalse((self.activity / 'maintenance').exists())

    def test_partial_static_failure_recovers_without_leaking_diagnostic(self):
        result = self.install(self.change('static-bad.txt'))
        self.assertEqual(result['status'], 'recovered_previous_release')
        self.assertNotIn('private test diagnostic', self.receipt.read_text())
        self.assertIn('private test diagnostic', self.controller.log.read_text())

    def test_dependency_and_migration_releases_are_refused_before_stop(self):
        for name in ('requirements.txt', 'platform_server/community_dictionary/migrations/0999_new.py'):
            with self.subTest(name=name):
                result = self.install(self.change(name))
                self.assertEqual(result['status'], 'refused')
                self.assertEqual(self.controller.head(), self.base)
                self.assertIsNone(self.controller.local_session())

    def test_dirty_checkout_is_preserved(self):
        target = self.change()
        (self.repo / 'my-notes.txt').write_text('keep this')
        result = self.install(target)
        self.assertEqual(result['reason'], 'checkout_has_local_changes')
        self.assertEqual((self.repo / 'my-notes.txt').read_text(), 'keep this')

    def test_wrong_expected_commit_is_refused(self):
        result = self.install(self.change(), 'f' * 40)
        self.assertEqual(result['reason'], 'installed_commit_does_not_match_request')

    def test_off_main_commit_is_refused(self):
        self.git_at(self.origin, 'switch', '-c', 'unreviewed')
        result = self.install(self.change())
        self.assertEqual(result['status'], 'refused')
        self.assertEqual(self.controller.head(), self.base)

    def test_unrelated_origin_is_refused(self):
        with patch.object(runner, 'SOURCE', 'https://example.invalid/repo.git'):
            self.assertEqual(self.install(self.base)['reason'], 'unexpected_origin')

    def test_busy_lease_refuses_and_reopens_admission(self):
        lease = self.activity / 'active.lease'
        lease.touch()
        with patch.object(self.controller, 'drain', side_effect=runner.Stop('busy_or_stale_activity_lease')):
            result = self.install(self.change())
        self.assertEqual(result['status'], 'refused')
        self.assertTrue(lease.exists())
        self.assertFalse((self.activity / 'maintenance').exists())

    def test_existing_maintenance_gate_is_never_removed(self):
        gate = self.activity / 'maintenance'
        gate.write_text('operator')
        result = self.install(self.change())
        self.assertEqual(result['reason'], 'maintenance_already_active')
        self.assertEqual(gate.read_text(), 'operator')

    def test_failed_recovery_keeps_maintenance(self):
        with patch.object(self.controller, 'start_server', side_effect=runner.Stop('start_failed')):
            result = self.install(self.change())
        self.assertEqual(result['status'], 'recovery_required')
        self.assertTrue((self.activity / 'maintenance').exists())

    def test_interrupt_during_restart_recovers_previous_release(self):
        original = self.controller.start_server
        count = 0
        def interrupted_once():
            nonlocal count
            count += 1
            if count == 1:
                raise KeyboardInterrupt()
            original()
        with patch.object(self.controller, 'start_server', side_effect=interrupted_once):
            result = self.install(self.change())
        self.assertEqual(result['status'], 'recovered_previous_release')
        self.controller.ready(self.base)
        self.assertFalse((self.activity / 'maintenance').exists())

    def test_concurrent_installation_is_refused_without_removing_lock(self):
        with runner.locked(self.controller.state):
            with self.assertRaises(runner.Stop):
                self.install(self.base)
            self.assertTrue((self.controller.state / 'install.lock').is_dir())


class ProtocolTests(unittest.TestCase):
    def test_sha_rejects_refs_and_command_text(self):
        for value in ('main', '-x', 'a' * 39, 'a' * 40 + '; true', None):
            with self.assertRaises(runner.Stop):
                runner.sha(value)

    def test_path_gate_handles_all_names_in_renamed_file_diff(self):
        self.assertEqual(runner.blocked_paths(['src/code.py', 'platform_server/x/migrations/0002_x.py']),
                         ['platform_server/x/migrations/0002_x.py'])
        for path in ('ops/a.py', '.github/workflows/x.yml', 'requirements-dev.txt', 'pyproject.toml', 'src/core/deployment_activity.py', 'src/django_q/tasks.py'):
            self.assertEqual(runner.blocked_paths([path]), [path])

    def test_receipt_requires_exact_laptop_commit(self):
        request = {'commit':'a' * 40, 'expected_laptop':'b' * 40}
        receipt = {'schema':1, 'status':'installed', 'target':'laptop',
                   'commit':'a' * 40, 'previous':'b' * 40}
        cloud.verify_receipt(receipt, request)
        for field, value in (('status','refused'), ('target','aws'), ('commit','c' * 40), ('previous','d' * 40)):
            with self.subTest(field=field), self.assertRaises(runner.Stop):
                cloud.verify_receipt(dict(receipt, **{field:value}), request)

    def test_run_proof_rejects_wrong_workflow_ref_status_or_event(self):
        value = {'conclusion':'success', 'event':'workflow_dispatch', 'head_branch':'main',
                 'head_sha':'a' * 40, 'path':'.github/workflows/laptop.yml',
                 'updated_at':datetime.now(timezone.utc).isoformat()}
        cloud.verify_run(value, 'a' * 40)
        for field, bad in (('event','pull_request'), ('conclusion','failure'), ('head_branch','other'),
                           ('head_sha','b' * 40), ('path','.github/workflows/other.yml'),
                           ('updated_at','2020-01-01T00:00:00Z')):
            with self.subTest(field=field), self.assertRaises(runner.Stop):
                cloud.verify_run(dict(value, **{field:bad}), 'a' * 40)

    def test_aws_needs_the_human_dispatch_before_any_network_call(self):
        with patch.dict(os.environ, {'GITHUB_ACTOR':'agent', 'HUMAN_APPROVER':'manny',
                                    'GITHUB_EVENT_NAME':'workflow_dispatch', 'GITHUB_REF':'refs/heads/main'}):
            with patch.object(cloud, 'proof') as proof, self.assertRaises(runner.Stop):
                cloud.deploy_aws({}, 'unused.json')
            proof.assert_not_called()


class CloudExecutionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.receipt = Path(self.temp.name) / 'result.json'
        self.request = {'commit': 'a' * 40, 'expected_aws': 'b' * 40}
        self.env = patch.dict(os.environ, {'GITHUB_ACTOR':'manny', 'HUMAN_APPROVER':'manny',
            'GITHUB_EVENT_NAME':'workflow_dispatch', 'GITHUB_REF':'refs/heads/main',
            'CLARA_INSTANCE_ID':'i-1234567890abcdef0'})
        self.env.start()
        self.proof = patch.object(cloud, 'proof', return_value=42)
        self.proof.start()

    def tearDown(self):
        self.proof.stop()
        self.env.stop()
        self.temp.cleanup()

    def test_one_command_and_verified_success_receipt(self):
        host = dict(schema=1, target='aws', status='installed', commit='a' * 40)
        invocation = {'Status':'Success', 'StandardOutputContent':json.dumps(host)}
        reply = subprocess.CompletedProcess([], 0, json.dumps(invocation), '')
        with patch.object(cloud, 'call', return_value={'Command':{'CommandId':'command-1'}}) as send:
            with patch.object(cloud.subprocess, 'run', return_value=reply), redirect_stdout(io.StringIO()):
                cloud.deploy_aws(self.request, self.receipt)
        send.assert_called_once()
        arguments = send.call_args.args[0]
        self.assertIn('CLARA-DeployCode', arguments)
        self.assertIn('1', arguments)
        self.assertEqual(json.loads(self.receipt.read_text())['laptop_run'], 42)

    def test_poll_failure_keeps_command_id_without_resubmitting(self):
        reply = subprocess.CompletedProcess([], 1, '', 'Network unavailable')
        with patch.object(cloud, 'call', return_value={'Command':{'CommandId':'command-2'}}) as send:
            with patch.object(cloud.subprocess, 'run', return_value=reply), self.assertRaises(runner.Stop):
                cloud.deploy_aws(self.request, self.receipt)
        send.assert_called_once()
        saved = json.loads(self.receipt.read_text())
        self.assertEqual(saved['command_id'], 'command-2')
        self.assertEqual(saved['status'], 'submitted')

    def test_successful_command_with_wrong_release_is_not_success(self):
        invocation = {'Status':'Success', 'StandardOutputContent':json.dumps(
            dict(target='aws', status='installed', commit='c' * 40))}
        reply = subprocess.CompletedProcess([], 0, json.dumps(invocation), '')
        with patch.object(cloud, 'call', return_value={'Command':{'CommandId':'command-3'}}):
            with patch.object(cloud.subprocess, 'run', return_value=reply), self.assertRaises(runner.Stop):
                cloud.deploy_aws(self.request, self.receipt)
        self.assertEqual(json.loads(self.receipt.read_text())['status'], 'submitted')


class PreparationTests(unittest.TestCase):
    def test_bootstrap_prepares_outside_checkout_and_refuses_overwrite(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / 'deployment'
            command = [sys.executable, str(HERE / 'bootstrap.py'), '--destination', str(target)]
            result = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            config = json.loads((target / 'laptop.json').read_text())
            self.assertEqual(config['target'], 'laptop')
            self.assertTrue((target / 'control/.github/workflows/aws.yml').is_file())
            self.assertTrue((target / 'bin/runner.py').is_file())
            self.assertNotEqual(subprocess.run(command, capture_output=True).returncode, 0)

    def test_drain_waits_for_active_lease(self):
        import threading
        import time
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            lease = root / 'task.lease'
            lease.touch()
            controller = object.__new__(runner.Controller)
            controller.activity, controller.timeout = root, 5
            finished = threading.Event()
            thread = threading.Thread(target=lambda: (controller.drain(), finished.set()))
            thread.start()
            try:
                self.assertFalse(finished.wait(0.1))
                lease.unlink()
                self.assertTrue(finished.wait(2))
            finally:
                lease.unlink(missing_ok=True)
                thread.join(6)


if __name__ == '__main__':
    unittest.main()
