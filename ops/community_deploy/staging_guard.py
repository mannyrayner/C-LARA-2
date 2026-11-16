#!/usr/bin/env python3
"""Root-owned staging boot gate and local expiry guard. Never extends a lease.

Install outside the application checkout. A trusted bootstrap supplies the
fixed-instance config and a read-only S3 client. READY is sent only after the
original deadline and synchronized boot clock have been checked. The process
then enforces both wall and elapsed time without further cloud access.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import socket
import subprocess
import time
import urllib.request
import uuid

try:
    from .staging_lifecycle import Refused, require, seconds, sha
    from .staging_aws import S3State
except ImportError:
    from staging_lifecycle import Refused, require, seconds, sha
    from staging_aws import S3State


class Guard:
    def __init__(self, instance, policy_revision, clock=time.time, elapsed=time.monotonic):
        self.instance, self.policy_revision = instance, sha(policy_revision)
        self.clock, self.elapsed = clock, elapsed
        self.lease_id, self.deadline, self.elapsed_deadline = None, None, None

    def arm(self, state, synchronized):
        require(self.lease_id is None, 'guard_already_armed')
        require(synchronized is True, 'boot_clock_not_synchronized')
        require(type(state) is dict and state.get('schema') == 1 and
                state.get('instance_id') == self.instance and
                state.get('policy_revision') == self.policy_revision and
                state.get('recovery_required') is False, 'boot_lease_scope_mismatch')
        request = state.get('active')
        session = state.get('requests', {}).get(request)
        require(type(session) is dict and session.get('phase') in
                {'starting', 'ready', 'testing'}, 'boot_lease_missing_or_stopping')
        now = int(self.clock())
        start, deadline = seconds(session.get('armed_at')), seconds(session.get('deadline'))
        require(start <= now < deadline and 0 < deadline - start <= 120 * 60,
                'boot_lease_expired_or_invalid')
        lease_id = session.get('lease_id')
        require(isinstance(lease_id, str) and str(uuid.UUID(lease_id)) == lease_id,
                'boot_lease_identity')
        self.lease_id, self.deadline = lease_id, deadline
        self.elapsed_deadline = self.elapsed() + deadline - now
        return {'lease_id': lease_id, 'deadline': deadline}

    def remaining(self):
        require(self.lease_id is not None, 'guard_not_armed')
        # Moving the wall clock backwards cannot increase the remaining lease.
        return max(0, min(self.deadline - self.clock(), self.elapsed_deadline - self.elapsed()))


def notify_ready():
    address = os.environ.get('NOTIFY_SOCKET')
    require(isinstance(address, str) and bool(address), 'systemd_notify_socket_required')
    if address.startswith('@'):
        address = '\0' + address[1:]
    with socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM) as stream:
        stream.connect(address)
        stream.sendall(b'READY=1')


def shutdown():
    # EC2 bootstrap must independently verify instance-initiated behavior is stop.
    subprocess.run(['/usr/bin/systemctl', 'poweroff', '--no-block'], check=True, timeout=10)


def marker_path():
    return Path('/run/clara-staging-deploy/lease.json')


def publish_marker(config, lease):
    path = marker_path()
    path.parent.mkdir(mode=0o755, parents=True, exist_ok=True)
    info = path.parent.stat()
    require(info.st_uid == 0 and info.st_mode & 0o022 == 0, 'root_owned_marker_directory_required')
    digest = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    require(digest == config['guard_sha256'], 'installed_guard_digest_mismatch')
    value = dict(lease, policy_revision=config['policy_revision'],
                 guard_revision=sha(config['guard_revision']), guard_sha256=digest)
    temporary = path.with_name(uuid.uuid4().hex + '.tmp')
    try:
        with temporary.open('x', encoding='utf-8') as stream:
            os.chmod(temporary, 0o644)
            json.dump(value, stream)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def revoke_marker():
    marker_path().unlink(missing_ok=True)


def instance_identity():
    """Use IMDSv2 only, with fixed link-local endpoints and bounded reads."""
    root = 'http://169.254.169.254/latest/'
    request = urllib.request.Request(root + 'api/token', method='PUT',
        headers={'X-aws-ec2-metadata-token-ttl-seconds': '60'})
    with urllib.request.urlopen(request, timeout=2) as response:
        token = response.read(4096).decode('ascii')
    request = urllib.request.Request(root + 'meta-data/instance-id',
        headers={'X-aws-ec2-metadata-token': token})
    with urllib.request.urlopen(request, timeout=2) as response:
        return response.read(128).decode('ascii').strip()


def verify_checkout(config, state):
    require(not (Path(config['activity_dir']) / 'maintenance').exists(),
            'boot_checkout_requires_reconciliation')
    for args, expected in [(['rev-parse', 'HEAD'], state['baseline']),
                           (['status', '--porcelain', '--untracked-files=normal'], '')]:
        result = subprocess.run(['/usr/bin/git', '-c', 'safe.directory=' + config['repo'],
                                 '-C', config['repo'], *args],
                                capture_output=True, text=True, timeout=10, check=True)
        require(result.stdout.strip() == expected, 'boot_checkout_requires_reconciliation')


def run(config, store, clock, elapsed, synchronized, notify, poweroff, sleep=time.sleep,
        checkout_check=verify_checkout, publish=None, revoke=None):
    guard = Guard(config['instance_id'], config['policy_revision'], clock, elapsed)
    try:
        state, _token = store.read()
        lease = guard.arm(state, synchronized())
        checkout_check(config, state)
        require(callable(publish) and callable(revoke), 'guard_marker_callbacks_required')
        publish(config, lease)
        notify()
        while guard.remaining() > 0:
            sleep(min(1, guard.remaining()))
    finally:
        # Missing lease, boot errors, expiry and process interruption all stop the host.
        try:
            if callable(revoke):
                revoke()
        finally:
            poweroff()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', required=True)
    args = parser.parse_args()
    require(os.geteuid() == 0, 'root_guard_required')
    authorized_host = False
    try:
        path = Path(args.config)
        require(path.stat().st_uid == 0 and path.stat().st_mode & 0o022 == 0,
                'root_owned_guard_config_required')
        config = json.loads(path.read_text(encoding='utf-8'))
        require(instance_identity() == config['instance_id'], 'boot_instance_mismatch')
        authorized_host = True
        # Trusted, root-owned config is outside the application checkout.
        import boto3
        from botocore.config import Config
        client = boto3.client('s3', region_name=config['region'],
                             config=Config(connect_timeout=2, read_timeout=3,
                                           retries={'total_max_attempts': 1}))
        store = S3State(client, config['state_bucket'], config['state_key'])
        def synchronized():
            reply = subprocess.run(['/usr/bin/timedatectl', 'show', '--property=NTPSynchronized',
                                    '--value'], capture_output=True, text=True, timeout=5, check=True)
            return reply.stdout.strip() == 'yes'
        elapsed = lambda: time.clock_gettime(time.CLOCK_BOOTTIME)
        run(config, store, time.time, elapsed, synchronized, notify_ready, shutdown,
            publish=publish_marker, revoke=revoke_marker)
    except Exception:
        # Catch configuration/import errors that occur before run's own finally.
        if authorized_host:
            shutdown()
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
