#!/usr/bin/env python3
"""Stage-a controller. Install a reviewed copy OUTSIDE the application checkout.

Standard library only. Host configuration is trusted installation policy; a release
request contains commits, never shell commands. No migration or pip installation.
"""
import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import socket
import subprocess
import sys
import time
import urllib.request
import uuid
import warnings

VERSION = 1
SHA = re.compile(r'[0-9a-f]{40}')
SOURCE = 'https://github.com/mannyrayner/C-LARA-2.git'


class Stop(Exception):
    """A deliberately non-sensitive, stable reason code."""


def sha(value):
    if not isinstance(value, str) or not SHA.fullmatch(value):
        raise Stop('invalid_commit')
    return value


def timestamp():
    return datetime.now(timezone.utc).isoformat()


def atomic_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + '.' + uuid.uuid4().hex + '.tmp')
    try:
        with temporary.open('x', encoding='utf-8') as stream:
            os.chmod(temporary, 0o600)
            json.dump(value, stream, indent=2)
            stream.write('\n')
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def read_request(path):
    value = json.loads(Path(path).read_text(encoding='utf-8'))
    if value.get('schema') != 1 or value.get('rollback_compatible') is not True:
        raise Stop('reviewed_code_only_request_required')
    for key in ('commit', 'expected_laptop', 'expected_aws'):
        sha(value.get(key))
    return value


def blocked_paths(paths):
    blocked = []
    integration = {
        'src/core/deployment_activity.py', 'src/django_q/tasks.py',
        'platform_server/community_dictionary/deployment_health.py',
        'platform_server/community_dictionary/management/commands/community_deployment_check.py',
        'platform_server/projects/management/commands/process_project_understanding_queue.py',
    }
    for value in paths:
        p = value.lower()
        name = p.rsplit('/', 1)[-1]
        if ('/migrations/' in '/' + p or name.startswith('requirements') or
                name in {'pyproject.toml', 'setup.py', 'setup.cfg', 'pipfile', 'pipfile.lock',
                         'poetry.lock', 'uv.lock', 'package.json', 'package-lock.json'} or
                p.startswith(('ops/', '.github/')) or p in integration):
            blocked.append(value)
    return blocked


@contextmanager
def locked(state):
    lock = state / 'install.lock'
    try:
        lock.mkdir()
    except FileExistsError:
        raise Stop('deployment_locked_inspect_before_recovery') from None
    try:
        atomic_json(lock / 'owner.json', {'pid': os.getpid(), 'started': timestamp()})
        yield
    finally:
        (lock / 'owner.json').unlink(missing_ok=True)
        lock.rmdir()


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


class Controller:
    def __init__(self, config_path):
        self.config_path = Path(config_path).resolve()
        self.config = json.loads(self.config_path.read_text(encoding='utf-8'))
        self.target = self.config['target']
        if self.target not in {'laptop', 'aws'}:
            raise Stop('invalid_target')
        for key in ('repo', 'state', 'activity_dir'):
            if not Path(self.config[key]).is_absolute():
                raise Stop('host_paths_must_be_absolute')
        self.repo = Path(self.config['repo']).resolve()
        self.state = Path(self.config['state']).resolve()
        self.activity = Path(self.config['activity_dir']).resolve()
        if self.state.is_relative_to(self.repo) or self.activity.is_relative_to(self.repo):
            raise Stop('deployment_state_must_be_outside_checkout')
        if not self.activity.is_dir():
            raise Stop('activity_directory_not_installed')
        self.state.mkdir(mode=0o700, parents=True, exist_ok=True)
        self.report = {'schema': VERSION, 'target': self.target, 'started': timestamp(), 'steps': []}
        self.log = self.state / ('install-' + uuid.uuid4().hex + '.log')
        self.env = dict(os.environ, CLARA_DEPLOY_ACTIVITY_DIR=str(self.activity))
        self.timeout = int(self.config.get('timeout_seconds', 120))
        if not 5 <= self.timeout <= 600:
            raise Stop('invalid_timeout')

    def command(self, name, args, cwd=None, check=True):
        # Never shell=True, never return raw stdout/stderr in a release receipt.
        try:
            result = subprocess.run(args, cwd=cwd or self.repo, env=self.env, capture_output=True,
                                    text=True, encoding='utf-8', errors='replace', timeout=self.timeout)
        except (OSError, subprocess.SubprocessError):
            self.report['steps'].append({'step': name, 'ok': False})
            raise Stop(name + '_could_not_complete') from None
        with self.log.open('a', encoding='utf-8') as stream:
            os.chmod(self.log, 0o600)
            stream.write('\nSTEP ' + name + '\n' + result.stdout + result.stderr)
        self.report['steps'].append({'step': name, 'ok': result.returncode == 0})
        if check and result.returncode:
            raise Stop(name + '_failed')
        return result

    def git(self, *args, check=True):
        return self.command('git_' + args[0].replace('-', '_'),
                            [self.config.get('git', 'git'), *args], check=check)

    def head(self):
        return sha(self.git('rev-parse', 'HEAD').stdout.strip())

    def clean(self):
        if self.git('status', '--porcelain', '--untracked-files=normal').stdout.strip():
            raise Stop('checkout_has_local_changes')

    def manage(self, *args, static=False):
        prefix = self.config.get('static_manage' if static else 'manage')
        if not isinstance(prefix, list) or not prefix or not all(isinstance(x, str) for x in prefix):
            raise Stop('invalid_host_command_configuration')
        return self.command('manage_' + args[0], [*prefix, *args], self.repo / 'platform_server')

    def preflight(self):
        self.manage('check')
        self.manage('makemigrations', '--check', '--dry-run')
        self.manage('community_deployment_check', '--activity-dir', str(self.activity),
                    '--backend', 'sqlite' if self.target == 'laptop' else 'postgresql')

    def drain(self):
        deadline = time.monotonic() + self.timeout
        while True:
            if not list(self.activity.glob('*.lease')):
                return
            if time.monotonic() >= deadline:
                raise Stop('busy_or_stale_activity_lease')
            time.sleep(0.25)

    def local_session(self):
        marker = self.state / 'server.json'
        if not marker.exists():
            return None
        session = json.loads(marker.read_text(encoding='utf-8')).get('session', '')
        if not re.fullmatch(r'[0-9a-f]{32}', session):
            raise Stop('invalid_local_server_record')
        return self.state / 'servers' / session

    def port_open(self):
        address = self.config.get('address', '127.0.0.1:8000')
        if not re.fullmatch(r'127\.0\.0\.1:[0-9]{4,5}', address):
            raise Stop('local_server_must_bind_loopback')
        try:
            with socket.create_connection(('127.0.0.1', int(address.split(':')[1])), timeout=1):
                return True
        except OSError:
            return False

    def stop_server(self):
        if self.target == 'aws':
            self.command('stop_services', self.config['stop'])
            self.command('verify_services_stopped', self.config['stopped'])
            return
        session = self.local_session()
        if session and not (session / 'exited').exists():
            (session / 'stop').touch()
            deadline = time.monotonic() + self.timeout
            while not (session / 'exited').exists():
                if time.monotonic() >= deadline:
                    raise Stop('local_supervisor_did_not_stop')
                time.sleep(0.2)
        if session and os.name == 'nt':
            # The marker acknowledges shutdown; wait for the supervisor itself
            # to exit too, so Windows releases its inherited log handles.
            import ctypes
            from ctypes import wintypes
            pid = json.loads((self.state / 'server.json').read_text(encoding='utf-8')).get('pid')
            if not isinstance(pid, int) or pid <= 0:
                raise Stop('local_supervisor_pid_missing')
            kernel = ctypes.WinDLL('kernel32', use_last_error=True)
            kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
            kernel.OpenProcess.restype = wintypes.HANDLE
            kernel.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
            kernel.WaitForSingleObject.restype = wintypes.DWORD
            kernel.CloseHandle.argtypes = [wintypes.HANDLE]
            handle = kernel.OpenProcess(0x00100000, False, pid)  # SYNCHRONIZE only
            if handle:
                try:
                    if kernel.WaitForSingleObject(handle, self.timeout * 1000) != 0:
                        raise Stop('local_supervisor_did_not_exit')
                finally:
                    kernel.CloseHandle(handle)
            elif ctypes.get_last_error() != 87:  # already-exited PID
                raise Stop('could_not_verify_local_supervisor_exit')
        if self.port_open():
            raise Stop('unmanaged_server_on_local_port')

    def start_server(self):
        if self.target == 'aws':
            self.command('start_services', self.config['start'])
            self.command('verify_services_running', self.config['running'])
            return
        if self.port_open():
            raise Stop('local_port_already_in_use')
        token = uuid.uuid4().hex
        session = self.state / 'servers' / token
        session.mkdir(parents=True)
        env = {k: v for k, v in self.env.items()
               if not k.startswith(('GITHUB_', 'GH_', 'ACTIONS_', 'RUNNER_'))}
        kwargs = {'creationflags': subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP} if os.name == 'nt' else {'start_new_session': True}
        with (session / 'server.log').open('wb') as stream:
            os.chmod(session / 'server.log', 0o600)
            # This supervisor deliberately outlives the workflow process. Its
            # lifecycle is controlled by the stop/exited handshake below.
            with warnings.catch_warnings():
                warnings.simplefilter('ignore', ResourceWarning)
                process = subprocess.Popen([sys.executable, '-E', str(Path(__file__).resolve()), 'serve',
                                           '--config', str(self.config_path), '--session', token],
                                          stdin=subprocess.DEVNULL, stdout=stream, stderr=stream,
                                          cwd=self.state, env=env, **kwargs)
                pid = process.pid
                del process
        atomic_json(self.state / 'server.json', {'session': token, 'pid': pid})

    def ready(self, commit):
        url = self.config['health_url']
        if not (url.startswith('https://') or url.startswith('http://127.0.0.1:')):
            raise Stop('health_url_requires_https_or_loopback')
        opener = urllib.request.build_opener(NoRedirect)
        deadline = time.monotonic() + self.timeout
        while True:
            try:
                request = urllib.request.Request(url, headers={'Cache-Control': 'no-cache'})
                with opener.open(request, timeout=5) as response:
                    data = json.loads(response.read(8192))
                    if response.status == 200 and data.get('ready') is True and data.get('release') == commit:
                        return
            except (OSError, ValueError):
                pass
            if time.monotonic() >= deadline:
                raise Stop('readiness_or_release_identity_failed')
            time.sleep(0.5)

    def install(self, commit, expected, receipt):
        commit, expected = sha(commit), sha(expected)
        self.report.update(commit=commit, previous=expected, status='checking')
        stopped = False
        owns_gate = False
        gate = self.activity / 'maintenance'
        with locked(self.state):
            try:
                self.clean()
                if self.head() != expected:
                    raise Stop('installed_commit_does_not_match_request')
                origin = self.git('remote', 'get-url', 'origin').stdout.strip()
                if origin.rstrip('/').removesuffix('.git') != SOURCE.rstrip('/').removesuffix('.git'):
                    raise Stop('unexpected_origin')
                self.git('fetch', '--no-tags', 'origin', 'main')
                self.git('merge-base', '--is-ancestor', commit, 'FETCH_HEAD')
                self.git('merge-base', '--is-ancestor', expected, commit)
                paths = self.git('diff', '--no-renames', '--name-only', expected, commit).stdout.splitlines()
                if blocked_paths(paths):
                    raise Stop('schema_dependencies_or_controller_changed_manual_release_required')
                self.preflight()
                if self.target == 'aws' or self.port_open():
                    if self.target == 'laptop' and self.local_session() is None:
                        raise Stop('stop_existing_manual_server_once_before_bootstrap')
                    self.ready(expected)
                # Exclusive creation also prevents interfering with an operator's
                # independently placed maintenance gate.
                try:
                    with gate.open('x', encoding='utf-8') as stream:
                        stream.write(commit + '\n')
                except FileExistsError:
                    raise Stop('maintenance_already_active') from None
                owns_gate = True
                self.drain()
                stopped = True  # a partially completed stop also needs recovery
                self.stop_server()
                self.clean()
                if self.head() != expected:
                    raise Stop('checkout_changed_during_installation')
                self.git('merge', '--ff-only', commit)
                self.preflight()
                self.manage('collectstatic', '--noinput', static=True)
                self.start_server()
                self.ready(commit)
                self.report['status'] = 'installed'
            except BaseException as exc:
                self.report['reason'] = str(exc) if isinstance(exc, Stop) else ('controller_interrupted' if isinstance(exc, KeyboardInterrupt) else 'unexpected_controller_error')
                self.report['status'] = 'refused'
                if stopped:
                    self.report['status'] = 'recovery_required'
                    try:
                        self.stop_server()
                        self.clean()
                        current = self.head()
                        if current not in {commit, expected}:
                            raise Stop('unexpected_checkout_during_recovery')
                        if current != expected:
                            # --keep refuses to overwrite unexpected local edits.
                            self.git('reset', '--keep', expected)
                        self.manage('collectstatic', '--noinput', static=True)
                        self.start_server()
                        self.ready(expected)
                        self.report['status'] = 'recovered_previous_release'
                    except BaseException:
                        self.report['status'] = 'recovery_required'
            finally:
                # If recovery is uncertain, retain maintenance and require an
                # operator to inspect it rather than expose a half-installed app.
                if owns_gate and self.report['status'] != 'recovery_required':
                    gate.unlink(missing_ok=True)
                self.report['finished'] = timestamp()
                atomic_json(receipt, self.report)
        return self.report


def serve(config, session):
    controller = Controller(config)
    if controller.target != 'laptop' or not re.fullmatch(r'[0-9a-f]{32}', session):
        raise Stop('invalid_server_request')
    directory = controller.state / 'servers' / session
    child = None
    try:
        child = subprocess.Popen([*controller.config['manage'], 'runserver',
                                  controller.config.get('address', '127.0.0.1:8000'),
                                  '--noreload', '--insecure'],
                                 cwd=controller.repo / 'platform_server', env=controller.env)
        while child.poll() is None and not (directory / 'stop').exists():
            time.sleep(0.2)
    finally:
        if child is not None and child.poll() is None:
            child.terminate()
            try:
                child.wait(timeout=15)
            except subprocess.TimeoutExpired:
                child.kill()
                child.wait(timeout=10)
        (directory / 'exited').touch()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    install = commands.add_parser('install')
    install.add_argument('--config', required=True)
    install.add_argument('--request')
    install.add_argument('--commit')
    install.add_argument('--expected')
    install.add_argument('--receipt', required=True)
    server = commands.add_parser('serve')
    server.add_argument('--config', required=True)
    server.add_argument('--session', required=True)
    args = parser.parse_args()
    os.umask(0o022)
    try:
        if args.command == 'serve':
            serve(args.config, args.session)
            return 0
        controller = Controller(args.config)
        if args.request:
            if args.commit or args.expected:
                raise Stop('choose_request_or_exact_commits')
            request = read_request(args.request)
            commit, expected = request['commit'], request['expected_' + controller.target]
        else:
            commit, expected = sha(args.commit), sha(args.expected)
        result = controller.install(commit, expected, args.receipt)
        print(json.dumps(result))
        return 0 if result['status'] == 'installed' else 1
    except Exception as exc:
        result = {'schema': VERSION, 'status': 'controller_refused',
                  'reason': str(exc) if isinstance(exc, Stop) else 'invalid_configuration_or_request'}
        if getattr(args, 'receipt', None):
            atomic_json(args.receipt, result)
        print(json.dumps(result))
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
