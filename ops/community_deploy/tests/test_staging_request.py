"""Request identity, hostile input and CLI evidence for the no-AWS rehearsal."""
from copy import deepcopy
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from ops.community_deploy import staging_request as control


class StagingRequestTests(unittest.TestCase):
    def setUp(self):
        self.policy = {'schema': 1, 'mode': 'dry_run',
            'repository': 'example/staging-control', 'repository_id': 321,
            'default_branch': 'main', 'allowed_sender_ids': [42], 'max_lease_minutes': 120}
        self.request = {'schema': 1, 'commit': 'a' * 40,
                        'expected_staging': 'b' * 40, 'lease_minutes': 30}
        self.event = {'action': 'opened', 'repository': {'id': 321,
            'full_name': 'example/staging-control', 'private': True, 'default_branch': 'main'},
            'sender': {'id': 42, 'login': 'reviewed-sender'},
            'issue': {'id': 987, 'number': 5, 'state': 'open', 'user': {'id': 42},
                'repository_url': 'https://api.github.com/repos/example/staging-control',
                'title': control.TITLE, 'body': json.dumps(self.request)}}
        self.environment = {'GITHUB_EVENT_NAME': 'issues',
            'GITHUB_REPOSITORY': 'example/staging-control', 'GITHUB_REPOSITORY_ID': '321',
            'GITHUB_REF': 'refs/heads/main', 'GITHUB_SHA': 'c' * 40,
            'GITHUB_RUN_ID': '1234', 'GITHUB_RUN_ATTEMPT': '1',
            'GITHUB_ACTOR_ID': '42', 'GITHUB_ACTOR': 'reviewed-sender',
            'GITHUB_TRIGGERING_ACTOR': 'reviewed-sender'}

    def process(self, event=None, policy=None, environment=None):
        return control.process(json.dumps(self.policy if policy is None else policy),
            json.dumps(self.event if event is None else event),
            self.environment if environment is None else environment)

    def test_valid_receipt_binds_request_control_revision_and_run_without_claiming_deployment(self):
        receipt = self.process()
        self.assertEqual(receipt['outcome'], 'validated')
        self.assertEqual(receipt['request']['request_id'], '321:5')
        self.assertEqual(receipt['request']['control_commit'], 'c' * 40)
        self.assertEqual(receipt['request']['run_id'], '1234')
        self.assertEqual(receipt['request']['source_repository'], 'mannyrayner/C-LARA-2')
        for field in ['aws_contacted', 'deployment_performed', 'source_commit_verified', 'runtime_reserved']:
            self.assertIs(receipt[field], False)
        self.assertNotIn('body', json.dumps(receipt))

    def test_only_original_opened_issue_on_private_trusted_repository_and_ref(self):
        mutations = [
            ('action', 'edited'), ('action', 'reopened'),
            ('repository.private', False), ('repository.id', 322),
            ('repository.full_name', 'example/other'), ('repository.default_branch', 'other'),
            ('sender.id', 43), ('sender.id', True), ('sender.login', None),
            ('issue.user.id', 43), ('issue.repository_url', 'https://api.github.com/repos/example/other'),
            ('issue.number', 0), ('issue.number', True), ('issue.id', 0),
            ('issue.state', 'closed'), ('issue.title', control.TITLE + '\n'),
            ('issue.pull_request', {}),
        ]
        for path, value in mutations:
            with self.subTest(path=path, value=value):
                event = deepcopy(self.event)
                target = event
                keys = path.split('.')
                for key in keys[:-1]:
                    target = target[key]
                target[keys[-1]] = value
                self.assertEqual(self.process(event=event)['outcome'], 'refused')

    def test_runner_context_and_rerun_cannot_substitute_for_original_sender(self):
        for key, value in [
            ('GITHUB_EVENT_NAME', 'workflow_dispatch'), ('GITHUB_REPOSITORY', 'example/other'),
            ('GITHUB_REPOSITORY_ID', '322'), ('GITHUB_REF', 'refs/heads/feature'),
            ('GITHUB_SHA', 'main'), ('GITHUB_ACTOR_ID', '43'),
            ('GITHUB_TRIGGERING_ACTOR', 'another-operator'), ('GITHUB_RUN_ATTEMPT', '2'),
            ('GITHUB_RUN_ID', '0'), ('GITHUB_RUN_ID', '9' * 5000),
        ]:
            with self.subTest(key=key):
                environment = {**self.environment, key: value}
                self.assertEqual(self.process(environment=environment)['outcome'], 'refused')

    def test_request_is_exact_bounded_data_with_no_command_or_target_overrides(self):
        for key, value in [
            ('schema', True), ('schema', 1.0), ('commit', 'A' * 40),
            ('commit', '0' * 40), ('commit', 'main'), ('expected_staging', 'a' * 39),
            ('commit', '$(echo PRIVATE-UNTRUSTED-TEXT)'),
            ('lease_minutes', True), ('lease_minutes', 30.5),
            ('lease_minutes', 14), ('lease_minutes', 121),
            ('instance_id', 'i-production'), ('command', 'anything'),
        ]:
            with self.subTest(key=key, value=value):
                event = deepcopy(self.event)
                event['issue']['body'] = json.dumps({**self.request, key: value})
                receipt = self.process(event=event)
                self.assertEqual(receipt['outcome'], 'refused')
                self.assertNotIn('PRIVATE-UNTRUSTED-TEXT', json.dumps(receipt))
        for key in self.request:
            event = deepcopy(self.event)
            request = {k: v for k, v in self.request.items() if k != key}
            event['issue']['body'] = json.dumps(request)
            self.assertEqual(self.process(event=event)['reason'], 'request_fields')

    def test_duplicate_nonstandard_oversized_and_invalid_unicode_json_is_refused(self):
        bodies = [
            '{"schema":1,"schema":1}', '{"schema":NaN}', '[]', 'null',
            '\ud800', 'x' * 2049, '{"unfinished":',
        ]
        for body in bodies:
            with self.subTest(body=repr(body)[:60]):
                event = deepcopy(self.event)
                event['issue']['body'] = body
                self.assertEqual(self.process(event=event)['outcome'], 'refused')
        for text in ['{"action":"opened","action":"opened"}', '[' * 10000, 'x' * 1_048_577]:
            self.assertEqual(control.process(json.dumps(self.policy), text,
                self.environment)['outcome'], 'refused')

    def test_unconfigured_or_live_policy_cannot_enable_execution(self):
        for key, value in [
            ('mode', 'live'), ('schema', True), ('repository', control.SOURCE),
            ('repository_id', 0), ('repository_id', True), ('allowed_sender_ids', []),
            ('allowed_sender_ids', [42, 42]), ('allowed_sender_ids', [True]),
            ('max_lease_minutes', 121), ('max_lease_minutes', True),
            ('unexpected', 'ignored?'),
        ]:
            with self.subTest(key=key):
                self.assertEqual(self.process(policy={**self.policy, key: value})['outcome'], 'refused')
        example = Path(control.__file__).with_name('staging_control') / 'policy.example.json'
        receipt = control.process(example.read_text(), json.dumps(self.event), self.environment)
        self.assertEqual(receipt['reason'], 'policy_repository_id')

    def test_shorter_policy_limit_is_enforced_and_same_commit_rehearsal_is_allowed(self):
        event = deepcopy(self.event)
        request = {**self.request, 'expected_staging': self.request['commit'], 'lease_minutes': 15}
        event['issue']['body'] = json.dumps(request)
        policy = {**self.policy, 'max_lease_minutes': 15}
        self.assertEqual(self.process(event=event, policy=policy)['outcome'], 'validated')
        self.assertEqual(self.process(policy=policy)['reason'], 'request_lease')

    def test_cli_writes_retrievable_receipt_and_returns_nonzero_for_hostile_or_missing_input(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            policy, event, receipt = [root / name for name in ['policy.json', 'event.json', 'receipt.json']]
            policy.write_text(json.dumps(self.policy), encoding='utf-8')
            event.write_text(json.dumps(self.event), encoding='utf-8')
            command = [sys.executable, str(Path(control.__file__).resolve()),
                '--policy', str(policy), '--event', str(event), '--receipt', str(receipt)]
            environment = {**os.environ, **self.environment, 'AWS_SECRET_ACCESS_KEY': 'NEVER-ECHO-THIS'}
            result = subprocess.run(command, env=environment, text=True, capture_output=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(result.stdout), json.loads(receipt.read_text()))
            self.assertNotIn('NEVER-ECHO-THIS', result.stdout + result.stderr)
            self.event['issue']['body'] = '$(touch PRIVATE-MARKER)'
            event.write_text(json.dumps(self.event), encoding='utf-8')
            result = subprocess.run(command, env=environment, text=True, capture_output=True, cwd=root)
            self.assertEqual(result.returncode, 2)
            self.assertFalse((root / 'PRIVATE-MARKER').exists())
            self.assertNotIn('PRIVATE-MARKER', result.stdout + result.stderr)
            event.write_bytes(b'\xff')
            result = subprocess.run(command, env=environment, text=True, capture_output=True)
            self.assertEqual(json.loads(result.stdout)['reason'], 'invalid_utf8')
            event.unlink()
            result = subprocess.run(command, env=environment, text=True, capture_output=True)
            self.assertEqual(result.returncode, 2)
            self.assertEqual(json.loads(receipt.read_text())['reason'], 'input_file_unavailable')


if __name__ == '__main__':
    unittest.main()
