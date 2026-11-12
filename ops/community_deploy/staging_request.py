"""Validate the first staging request rehearsal. This module never calls AWS.

Copy this file to the root of the private staging control repository together
with staging_control/ templates. Requests and policy are data, never commands.
"""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re


SOURCE = 'mannyrayner/C-LARA-2'
TITLE = 'Deploy Community Dictionaries to staging'
SHA = re.compile(r'[0-9a-f]{40}')
REPOSITORY = re.compile(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+')
POLICY_KEYS = {'schema', 'mode', 'repository', 'repository_id', 'default_branch',
               'allowed_sender_ids', 'max_lease_minutes'}
REQUEST_KEYS = {'schema', 'commit', 'expected_staging', 'lease_minutes'}


class Refused(ValueError):
    """A fixed reason code safe to include in a private receipt or job log."""


def require(condition, reason):
    if not condition:
        raise Refused(reason)


def positive_integer(value):
    return type(value) is int and 0 < value < 2**63


def commit(value):
    return isinstance(value, str) and SHA.fullmatch(value) and value != '0' * 40


def object_pairs(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, 'duplicate_json_key')
        result[key] = value
    return result


def invalid_constant(_value):
    raise Refused('nonstandard_json_constant')


def json_object(text, limit):
    require(isinstance(text, str), 'json_object_required')
    try:
        size = len(text.encode('utf-8'))
    except UnicodeEncodeError:
        raise Refused('invalid_utf8') from None
    require(size <= limit, 'json_size_limit')
    try:
        value = json.loads(text, object_pairs_hook=object_pairs,
                           parse_constant=invalid_constant)
    except (ValueError, RecursionError) as error:
        if isinstance(error, Refused):
            raise
        raise Refused('invalid_json') from None
    require(type(value) is dict, 'json_object_required')
    return value


def policy_from_text(text):
    policy = json_object(text, 16_384)
    require(set(policy) == POLICY_KEYS, 'policy_fields')
    require(type(policy['schema']) is int and policy['schema'] == 1, 'policy_schema')
    require(policy['mode'] == 'dry_run', 'dry_run_policy_required')
    require(isinstance(policy['repository'], str) and
            REPOSITORY.fullmatch(policy['repository']) and
            policy['repository'] != SOURCE, 'policy_repository')
    require(positive_integer(policy['repository_id']), 'policy_repository_id')
    require(policy['default_branch'] == 'main', 'policy_default_branch')
    senders = policy['allowed_sender_ids']
    require(type(senders) is list and 0 < len(senders) <= 10 and
            all(positive_integer(sender) for sender in senders) and
            len(set(senders)) == len(senders), 'policy_senders')
    require(type(policy['max_lease_minutes']) is int and
            15 <= policy['max_lease_minutes'] <= 120, 'policy_lease_limit')
    return policy


def validate(event, policy, environment):
    """Return normalized data only; trust comes from the installed workflow."""
    require(environment.get('GITHUB_EVENT_NAME') == 'issues', 'event_name')
    require(event.get('action') == 'opened', 'event_action')
    require(environment.get('GITHUB_REPOSITORY') == policy['repository'], 'runner_repository')
    require(environment.get('GITHUB_REF') == 'refs/heads/' + policy['default_branch'],
            'runner_ref')
    require(commit(environment.get('GITHUB_SHA')), 'control_commit')
    require(environment.get('GITHUB_REPOSITORY_ID') == str(policy['repository_id']),
            'runner_repository_id')
    repository = event.get('repository')
    require(type(repository) is dict, 'event_repository')
    require(repository.get('private') is True, 'private_repository_required')
    require(type(repository.get('id')) is int and
            repository['id'] == policy['repository_id'] and
            repository.get('full_name') == policy['repository'] and
            repository.get('default_branch') == policy['default_branch'], 'event_repository')
    sender = event.get('sender')
    require(type(sender) is dict and positive_integer(sender.get('id')) and
            sender['id'] in policy['allowed_sender_ids'], 'sender_not_allowed')
    require(isinstance(sender.get('login'), str) and bool(sender['login']), 'sender_login')
    require(environment.get('GITHUB_ACTOR_ID') == str(sender['id']), 'runner_actor')
    require(environment.get('GITHUB_TRIGGERING_ACTOR') == environment.get('GITHUB_ACTOR') and
            environment.get('GITHUB_ACTOR') == sender.get('login'), 'runner_triggering_actor')
    issue = event.get('issue')
    require(type(issue) is dict and positive_integer(issue.get('number')) and
            positive_integer(issue.get('id')), 'event_issue')
    require('pull_request' not in issue and issue.get('state') == 'open', 'open_issue_required')
    require(issue.get('repository_url') ==
            'https://api.github.com/repos/' + policy['repository'], 'issue_repository')
    author = issue.get('user')
    require(type(author) is dict and type(author.get('id')) is int and
            author['id'] == sender['id'], 'issue_author')
    require(issue.get('title') == TITLE, 'issue_title')
    # The original webhook body is used, rather than a later mutable issue fetch.
    request = json_object(issue.get('body'), 2_048)
    require(set(request) == REQUEST_KEYS, 'request_fields')
    require(type(request['schema']) is int and request['schema'] == 1, 'request_schema')
    require(commit(request['commit']) and commit(request['expected_staging']), 'request_commits')
    require(type(request['lease_minutes']) is int and
            15 <= request['lease_minutes'] <= policy['max_lease_minutes'], 'request_lease')
    require(environment.get('GITHUB_RUN_ATTEMPT') == '1', 'rerun_requires_new_request')
    run_id = environment.get('GITHUB_RUN_ID', '')
    require(isinstance(run_id, str) and len(run_id) <= 19 and run_id.isascii() and run_id.isdecimal() and
            positive_integer(int(run_id)), 'run_id')
    return {
        'request_id': f"{policy['repository_id']}:{issue['number']}",
        'issue_id': issue['id'], 'issue_number': issue['number'],
        'sender_id': sender['id'], 'repository': policy['repository'],
        'source_repository': SOURCE, 'control_commit': environment['GITHUB_SHA'],
        'run_id': run_id, 'run_attempt': 1, **request,
    }


def process(policy_text, event_text, environment):
    receipt = {'schema': 1, 'mode': 'dry_run', 'aws_contacted': False,
               'deployment_performed': False, 'source_commit_verified': False,
               'runtime_reserved': False,
               'recorded_at': datetime.now(timezone.utc).isoformat()}
    try:
        policy = policy_from_text(policy_text)
        event = json_object(event_text, 1_048_576)
        receipt['request'] = validate(event, policy, environment)
        receipt.update(outcome='validated', reason='request_shape_and_identity_only')
    except Refused as error:
        receipt.update(outcome='refused', reason=str(error))
    return receipt


def read_bounded(path, limit):
    with Path(path).open('rb') as stream:
        data = stream.read(limit + 1)
    require(len(data) <= limit, 'json_size_limit')
    try:
        return data.decode('utf-8')
    except UnicodeDecodeError:
        raise Refused('invalid_utf8') from None


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--policy', required=True)
    parser.add_argument('--event', required=True)
    parser.add_argument('--receipt', required=True)
    args = parser.parse_args(argv)
    try:
        policy_text = read_bounded(args.policy, 16_384)
        event_text = read_bounded(args.event, 1_048_576)
        receipt = process(policy_text, event_text, os.environ)
    except (OSError, Refused) as error:
        receipt = {'schema': 1, 'mode': 'dry_run', 'outcome': 'refused',
                   'reason': str(error) if isinstance(error, Refused) else 'input_file_unavailable',
                   'aws_contacted': False, 'deployment_performed': False,
                   'source_commit_verified': False, 'runtime_reserved': False}
    destination = Path(args.receipt)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(destination.suffix + '.tmp')
    temporary.write_text(json.dumps(receipt, indent=2) + '\n', encoding='utf-8')
    os.replace(temporary, destination)
    print(json.dumps(receipt, sort_keys=True))
    return 0 if receipt['outcome'] == 'validated' else 2


if __name__ == '__main__':
    raise SystemExit(main())
