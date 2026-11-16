#!/usr/bin/env python3
"""Fixed staging SSM entry point; rejects delayed commands for obsolete leases."""
import argparse
import json
from pathlib import Path
import subprocess
import time
import uuid

try:
    from .staging_lifecycle import require, sha
    from .staging_aws import S3State
except ImportError:
    from staging_lifecycle import require, sha
    from staging_aws import S3State


def assert_installable(state, config, candidate, expected, lease, now):
    sha(candidate), sha(expected)
    require(isinstance(lease, str) and str(uuid.UUID(lease)) == lease, 'invalid_lease_id')
    require(state.get('schema') == 1 and state.get('instance_id') == config['instance_id'] and
            state.get('policy_revision') == config['policy_revision'] and
            state.get('recovery_required') is False and state.get('baseline') == expected,
            'staging_lease_scope_mismatch')
    session = state.get('requests', {}).get(state.get('active'))
    require(type(session) is dict and session.get('lease_id') == lease and
            session.get('phase') == 'deploying' and session.get('commit') == candidate and
            session.get('expected_staging') == expected, 'staging_command_does_not_match_lease')
    require(type(session.get('deadline')) is int and type(session.get('armed_at')) is int and
            session['armed_at'] <= now < session['deadline'] and
            0 < session['deadline'] - session['armed_at'] <= 7200, 'staging_lease_expired')
    require(session.get('unknown', {}).get('stop') is False and
            session.get('unknown', {}).get('start') is False, 'staging_operation_unresolved')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', required=True)
    parser.add_argument('--commit', required=True)
    parser.add_argument('--expected', required=True)
    parser.add_argument('--lease', required=True)
    args = parser.parse_args()
    try:
        config = json.loads(Path(args.config).read_text(encoding='utf-8'))
        try:
            from .staging_guard import instance_identity
        except ImportError:
            from staging_guard import instance_identity
        require(instance_identity() == config['instance_id'], 'staging_instance_mismatch')
        import boto3
        from botocore.config import Config
        client = boto3.client('s3', region_name=config['region'],
                             config=Config(connect_timeout=2, read_timeout=3,
                                           retries={'total_max_attempts': 1}))
        state, _token = S3State(client, config['state_bucket'], config['state_key']).read()
        assert_installable(state, config, args.commit, args.expected, args.lease, int(time.time()))
        guard = subprocess.run(['/usr/bin/systemctl', 'is-active', 'clara-staging-lease.service'],
                               capture_output=True, text=True, timeout=5)
        require(guard.returncode == 0 and guard.stdout.strip() == 'active', 'staging_guard_not_active')
        result = subprocess.run(['/usr/bin/sudo', '-u', 'ssm-user', '/usr/bin/python3',
            '/opt/clara-staging-deploy/runner.py', 'install',
            '--config', '/etc/clara-staging-deploy.json', '--commit', args.commit,
            '--expected', args.expected, '--receipt', '/var/lib/clara-staging-deploy/result.json'],
            capture_output=True, text=True, timeout=1200)
        receipt = json.loads(result.stdout)
        require(type(receipt) is dict and receipt.get('target') == 'staging' and
                receipt.get('commit') == args.commit and receipt.get('previous') == args.expected,
                'staging_controller_receipt_unverified')
        require(int(time.time()) < state['requests'][state['active']]['deadline'],
                'staging_lease_expired_during_install')
        print(json.dumps(receipt))
        return 0 if result.returncode == 0 and receipt.get('status') == 'installed' else 1
    except Exception:
        # Retain no raw SDK, subprocess, configuration or credential diagnostics.
        print(json.dumps({'schema': 1, 'target': 'staging', 'status': 'recovery_required',
                          'reason': 'staging_command_not_verified'}))
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
