#!/usr/bin/env python3
"""Private-control-repository workflow helper. No application data is retrieved."""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import subprocess
import time
from runner import Stop, atomic_json, read_request, sha


def call(args):
    result = subprocess.run(args, capture_output=True, text=True, timeout=60)
    if result.returncode:
        raise Stop('control_api_call_failed')
    return json.loads(result.stdout)


def verify_run(run, control_sha):
    if (run.get('conclusion') != 'success' or run.get('event') != 'workflow_dispatch' or
            run.get('head_branch') != 'main' or run.get('head_sha') != control_sha or
            run.get('path') != '.github/workflows/laptop.yml'):
        raise Stop('latest_laptop_run_is_not_a_success_for_this_release_request')
    finished = datetime.fromisoformat(run['updated_at'].replace('Z', '+00:00'))
    age = (datetime.now(timezone.utc) - finished).total_seconds()
    if not 0 <= age <= 86400:
        raise Stop('laptop_result_is_older_than_24_hours_repeat_laptop_install')


def verify_receipt(receipt, request):
    if (receipt.get('schema') != 1 or receipt.get('status') != 'installed' or
            receipt.get('target') != 'laptop' or receipt.get('commit') != request['commit'] or
            receipt.get('previous') != request['expected_laptop']):
        raise Stop('laptop_receipt_does_not_match_release_request')


PROOF_FILES = ('current_release.json', '.github/workflows/laptop.yml', 'runner.py')


def verify_release_snapshot(repo, run_sha, control_sha, snapshots):
    """A helper-only update does not invalidate an unchanged laptop proof.

    Compare immutable Git blobs, not mutable branches or just the candidate
    commit. Changing the request, laptop workflow or controller requires a new
    laptop run. The proof must also remain in the control main's ancestry.
    """
    run_sha = sha(run_sha)
    if run_sha == control_sha:
        return
    comparison = call(['gh', 'api', f'repos/{repo}/compare/{run_sha}...{control_sha}'])
    if comparison.get('behind_by') != 0 or comparison.get('merge_base_commit', {}).get('sha') != run_sha:
        raise Stop('laptop_proof_is_not_from_control_main_history')
    def snapshot(commit):
        if commit not in snapshots:
            snapshots[commit] = tuple(sha(call(['gh', 'api',
                f'repos/{repo}/contents/{path}?ref={commit}']).get('sha')) for path in PROOF_FILES)
        return snapshots[commit]
    if snapshot(run_sha) != snapshot(control_sha):
        raise Stop('laptop_proof_release_request_or_installer_changed')


def proof(request):
    repo = os.environ['GITHUB_REPOSITORY']
    if not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', repo):
        raise Stop('invalid_control_repository')
    control_sha = sha(os.environ['GITHUB_SHA'])
    runs = call(['gh', 'api', f'repos/{repo}/actions/workflows/laptop.yml/runs?event=workflow_dispatch&branch=main&per_page=20'])['workflow_runs']
    if not runs:
        raise Stop('no_laptop_run')
    snapshots = {}
    for run in runs[:20]:
        # Validate identity before considering the narrow cancellation exception.
        if (run.get('status') != 'completed' or run.get('event') != 'workflow_dispatch' or run.get('head_branch') != 'main' or
                run.get('path') != '.github/workflows/laptop.yml'):
            raise Stop('latest_laptop_run_is_not_a_success_for_this_release_request')
        run_sha = sha(run.get('head_sha'))
        verify_release_snapshot(repo, run_sha, control_sha, snapshots)
        if run.get('status') == 'completed' and run.get('conclusion') == 'cancelled':
            jobs = call(['gh', 'api', f'repos/{repo}/actions/runs/{int(run["id"])}/jobs?per_page=1'])
            # Only a first-attempt queued cancellation with no jobs is harmless.
            # Earlier attempts of a re-run might already have touched the host.
            # Any started job, ambiguous response, failure or in-flight run blocks.
            if run.get('run_attempt') == 1 and jobs.get('total_count') == 0 and jobs.get('jobs') == []:
                print('Ignored queued cancellation of laptop run:', int(run['id']))
                continue
            raise Stop('cancelled_laptop_run_started_a_job_check_laptop_before_deploying')
        verify_run(run, run_sha)
        break
    else:
        raise Stop('no_successful_laptop_run_after_queued_cancellations')
    directory = Path('laptop-proof')
    if directory.exists():
        raise Stop('proof_directory_already_exists')
    result = subprocess.run(['gh', 'run', 'download', str(int(run['id'])), '--repo', repo,
                             '--name', 'laptop-receipt', '--dir', str(directory)],
                            capture_output=True, timeout=60)
    if result.returncode:
        raise Stop('could_not_download_laptop_receipt')
    receipt = json.loads((directory / 'receipt.json').read_text(encoding='utf-8'))
    verify_receipt(receipt, request)
    print('Verified successful laptop run:', int(run['id']))
    return int(run['id'])


def deploy_aws(request, receipt_file):
    # This check is independent of GitHub environment features/paid plans.
    actor, human = os.environ.get('GITHUB_ACTOR'), os.environ.get('HUMAN_APPROVER')
    if (not actor or not human or actor != human or
            os.environ.get('GITHUB_EVENT_NAME') != 'workflow_dispatch' or
            os.environ.get('GITHUB_REF') != 'refs/heads/main'):
        raise Stop('human_dispatch_on_control_main_required')
    laptop_run = proof(request)
    instance = os.environ['CLARA_INSTANCE_ID']
    if not re.fullmatch(r'i-[0-9a-f]{8,17}', instance):
        raise Stop('invalid_instance_id')
    parameters = {'Commit': [request['commit']], 'ExpectedCommit': [request['expected_aws']]}
    response = call(['aws', 'ssm', 'send-command', '--instance-ids', instance,
                     '--document-name', 'CLARA-DeployCode', '--document-version', '1',
                     '--parameters', json.dumps(parameters), '--timeout-seconds', '600', '--output', 'json'])
    command = response['Command']['CommandId']
    # Save the command ID before polling. A lost polling connection must not
    # become a second installation request.
    atomic_json(receipt_file, {'schema': 1, 'status': 'submitted', 'command_id': command,
                               'commit': request['commit'], 'laptop_run': laptop_run})
    deadline = time.monotonic() + 900
    while time.monotonic() < deadline:
        result = subprocess.run(['aws', 'ssm', 'get-command-invocation', '--command-id', command,
                                 '--instance-id', instance, '--output', 'json'],
                                capture_output=True, text=True, timeout=60)
        if result.returncode:
            if 'InvocationDoesNotExist' in result.stderr:
                time.sleep(3)
                continue
            raise Stop('polling_failed_inspect_saved_command_id_do_not_resubmit')
        invocation = json.loads(result.stdout)
        if invocation['Status'] in {'Pending', 'InProgress', 'Delayed'}:
            time.sleep(3)
            continue
        if invocation['Status'] != 'Success':
            atomic_json(receipt_file, {'schema': 1, 'status': 'aws_command_failed',
                'command_id': command, 'commit': request['commit'], 'laptop_run': laptop_run})
            raise Stop('aws_command_failed_inspect_host_receipt')
        try:
            receipt = json.loads(invocation['StandardOutputContent'].strip())
        except ValueError:
            raise Stop('invalid_host_receipt_inspect_command_id') from None
        if receipt.get('status') != 'installed' or receipt.get('commit') != request['commit'] or receipt.get('target') != 'aws':
            raise Stop('host_receipt_does_not_confirm_requested_release')
        receipt.update(command_id=command, laptop_run=laptop_run)
        atomic_json(receipt_file, receipt)
        print('AWS installed the accepted commit:', request['commit'])
        return
    raise Stop('polling_timeout_inspect_saved_command_id_do_not_resubmit')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--request', default='current_release.json')
    parser.add_argument('--receipt', default='aws-receipt.json')
    args = parser.parse_args()
    try:
        deploy_aws(read_request(args.request), args.receipt)
    except Stop as exc:
        print('Stopped:', exc)
        return 1
    except Exception:
        print('Stopped: control_error; inspect saved command ID before retrying.')
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
