"""Independent local expiry and stale internal SSM request checks; no cloud calls."""
from copy import deepcopy
from datetime import datetime, timezone
import io
import json
from unittest.mock import Mock
from types import SimpleNamespace
import unittest

from ops.community_deploy.staging_aws import FixedCloud, S3State
from ops.community_deploy.staging_guard import Guard, run
from ops.community_deploy.staging_install import assert_installable
from ops.community_deploy.staging_lifecycle import Refused, StateUnavailable
from ops.community_deploy.tests import test_staging_lifecycle as fixtures
from ops.community_deploy.tests.test_staging_lifecycle import BASE, CANDIDATE, CONTROL


class GuardTests(unittest.TestCase):
    def setUp(self):
        setup = fixtures.LifecycleTests()
        setup.setUp()
        self.clock, self.coordinator, self.store = setup.clock, setup.coordinator, setup.store
        self.session = self.coordinator.open(setup.request)
        self.now, self.elapsed = self.clock.now + 20, 100
        self.config = dict(instance_id=setup.policy.instance_id, policy_revision=CONTROL)

    def guard(self):
        return Guard(self.config['instance_id'], CONTROL, lambda: self.now, lambda: self.elapsed)

    def test_original_expiry_is_used_and_cannot_be_rearmed(self):
        guard = self.guard()
        guard.arm(self.store.value, True)
        self.assertEqual(guard.remaining(), 1780)
        with self.assertRaisesRegex(Refused, 'guard_already_armed'):
            guard.arm(self.store.value, True)

    def test_clock_rollback_does_not_extend_elapsed_deadline(self):
        guard = self.guard()
        guard.arm(self.store.value, True)
        self.now -= 600
        self.elapsed += 1781
        self.assertEqual(guard.remaining(), 0)

    def test_forward_wall_clock_jump_expires_immediately(self):
        guard = self.guard()
        guard.arm(self.store.value, True)
        self.now += 2000
        self.assertEqual(guard.remaining(), 0)

    def test_reboot_during_installation_or_without_lease_is_refused(self):
        states = []
        missing = deepcopy(self.store.value); missing['active'] = None; states.append(missing)
        for phase in ['deploying', 'stopping', 'closed']:
            state = deepcopy(self.store.value)
            state['requests'][state['active']]['phase'] = phase
            states.append(state)
        wrong = deepcopy(self.store.value); wrong['instance_id'] = 'i-production'; states.append(wrong)
        wrong = deepcopy(self.store.value); wrong['recovery_required'] = True; states.append(wrong)
        for state in states:
            with self.subTest(state=state), self.assertRaises(Refused):
                self.guard().arm(state, True)

    def test_unsynchronized_expired_and_future_boot_clocks_are_refused(self):
        with self.assertRaisesRegex(Refused, 'boot_clock_not_synchronized'):
            self.guard().arm(self.store.value, False)
        for now in [self.session['deadline'], self.session['armed_at'] - 1]:
            self.now = now
            with self.subTest(now=now), self.assertRaises(Refused):
                self.guard().arm(self.store.value, True)

    def test_local_shutdown_occurs_without_any_further_cloud_read(self):
        notify, poweroff, checkout = Mock(), Mock(), Mock()
        store = Mock(); store.read.return_value = (self.store.value, 'token')
        self.now = self.session['deadline'] - 2
        def sleep(seconds):
            self.now += seconds; self.elapsed += seconds
        run(self.config, store, lambda: self.now, lambda: self.elapsed,
            lambda: True, notify, poweroff, sleep=sleep, checkout_check=checkout,
            publish=Mock(), revoke=Mock())
        store.read.assert_called_once()
        notify.assert_called_once()
        poweroff.assert_called_once()
        checkout.assert_called_once()

    def test_cloud_or_checkout_failure_stops_before_app_readiness(self):
        for failed_checkout in [False, True]:
            store, notify, poweroff = Mock(), Mock(), Mock()
            checkout = Mock(side_effect=Refused('dirty_checkout') if failed_checkout else None)
            if failed_checkout:
                store.read.return_value = (self.store.value, 'token')
            else:
                store.read.side_effect = StateUnavailable('missing_lease')
            with self.assertRaises(Refused):
                run(self.config, store, lambda: self.now, lambda: self.elapsed,
                    lambda: True, notify, poweroff, checkout_check=checkout,
                    publish=Mock(), revoke=Mock())
            notify.assert_not_called()
            poweroff.assert_called_once()

    def test_internal_ssm_command_matches_original_active_lease(self):
        session = self.store.value['requests'][self.store.value['active']]
        session['phase'] = 'deploying'
        args = (self.store.value, self.config, CANDIDATE, BASE, self.session['lease_id'], self.now)
        assert_installable(*args)
        for field, value in [('lease_id', '00000000-0000-0000-0000-000000000000'),
                             ('commit', 'e' * 40), ('expected_staging', 'e' * 40),
                             ('deadline', self.now), ('phase', 'testing')]:
            state = deepcopy(self.store.value)
            state['requests'][state['active']][field] = value
            with self.subTest(field=field), self.assertRaises(Refused):
                assert_installable(state, *args[1:])


class AdapterTests(unittest.TestCase):
    def client(self):
        client = Mock()
        client.meta.config = SimpleNamespace(retries={'total_max_attempts': 1},
                                              connect_timeout=2, read_timeout=3)
        return client

    def test_s3_read_is_bounded_and_conditional_write_has_no_retry(self):
        client = self.client()
        stream = io.BytesIO(b'{"schema":1}')
        client.get_object.return_value = {'Body': stream, 'ETag': '"etag-1"'}
        client.put_object.return_value = {'ETag': '"etag-2"'}
        store = S3State(client, 'example-staging', 'staging/lifecycle.json')
        state, token = store.read()
        self.assertEqual(state, {'schema': 1})
        self.assertTrue(stream.closed)
        self.assertEqual(store.compare_and_swap(token, state), '"etag-2"')
        self.assertEqual(client.put_object.call_args.kwargs['IfMatch'], '"etag-1"')
        self.assertEqual(client.put_object.call_args.kwargs['ServerSideEncryption'], 'AES256')
        client.put_object.side_effect = TimeoutError('PRIVATE DIAGNOSTIC')
        with self.assertRaisesRegex(StateUnavailable, '^conditional_state_write_unconfirmed$'):
            store.compare_and_swap(token, state)
        self.assertEqual(client.put_object.call_count, 2)

    def test_state_missing_oversized_or_conditional_conflict_never_auto_initializes(self):
        client = self.client()
        store = S3State(client, 'example-staging', 'staging/lifecycle.json', max_bytes=10)
        client.get_object.side_effect = OSError()
        with self.assertRaises(StateUnavailable):
            store.read()
        client.get_object.side_effect = None
        client.get_object.return_value = {'Body': io.BytesIO(b' ' * 11), 'ETag': 'x'}
        with self.assertRaises(StateUnavailable):
            store.read()
        client.put_object.assert_not_called()

    def cloud(self):
        ec2, ssm = self.client(), self.client()
        cloud = FixedCloud(ec2, ssm, 'i-1234567890abcdef0', '1', lambda revision: True,
                           lambda expected, lease: True)
        return cloud, ec2, ssm

    def test_sdk_automatic_retries_and_unbounded_timeouts_are_refused(self):
        client = self.client()
        client.meta.config.retries = {'total_max_attempts': 3}
        with self.assertRaisesRegex(Refused, 'sdk_retries_must_be_disabled'):
            S3State(client, 'example-staging', 'staging/lifecycle.json')
        client.meta.config.retries = {'total_max_attempts': 1}
        client.meta.config.read_timeout = 60
        with self.assertRaisesRegex(Refused, 'sdk_timeouts_must_be_bounded'):
            S3State(client, 'example-staging', 'staging/lifecycle.json')

    def test_cloud_mutations_cannot_select_another_instance_or_document(self):
        cloud, ec2, ssm = self.cloud()
        ec2.describe_instances.return_value = {'Reservations': [{'Instances': [
            {'InstanceId': cloud.instance, 'State': {'Name': 'stopped'}}]}]}
        ec2.describe_instance_attribute.return_value = {'InstanceInitiatedShutdownBehavior': {'Value': 'stop'}}
        cloud.verify_guards(CONTROL)
        self.assertEqual(cloud.instance_state(), 'stopped')
        cloud.start(); cloud.stop()
        lease = '00000000-0000-0000-0000-000000000001'
        ssm.send_command.return_value = {'Command': {'CommandId': lease}}
        self.assertEqual(cloud.deploy(CANDIDATE, BASE, lease), lease)
        for call in [ec2.start_instances.call_args, ec2.stop_instances.call_args]:
            self.assertEqual(call.kwargs, {'InstanceIds': [cloud.instance]})
        args = ssm.send_command.call_args.kwargs
        self.assertEqual(args['DocumentName'], 'CLARA-DeployStaging')
        self.assertEqual(args['DocumentVersion'], '1')
        self.assertEqual(args['Parameters']['LeaseId'], [lease])

    def test_wrong_shutdown_behavior_identity_and_missing_probe_are_refused(self):
        cloud, ec2, _ = self.cloud()
        ec2.describe_instance_attribute.return_value = {'InstanceInitiatedShutdownBehavior': {'Value': 'terminate'}}
        with self.assertRaisesRegex(Refused, 'host_shutdown_must_stop'):
            cloud.verify_guards(CONTROL)
        ec2.describe_instances.return_value = {'Reservations': [{'Instances': [
            {'InstanceId': 'i-fffffffffffffffff', 'State': {'Name': 'stopped'}}]}]}
        with self.assertRaises(Refused):
            cloud.instance_state()
        cloud.guard_probe = lambda revision: False
        with self.assertRaises(Refused):
            cloud.verify_guards(CONTROL)

    def test_terminal_command_requires_parsable_receipt_and_consistent_exit(self):
        cloud, _, ssm = self.cloud()
        for status, text, expected in [('InProgress', '', None), ('Failed', 'not json', {}),
                                      ('Success', '[]', {}),
                                      ('Failed', '{"status":"installed"}', {}),
                                      ('Failed', '{"status":"recovered_previous_release"}',
                                       {'status': 'recovered_previous_release'})]:
            ssm.get_command_invocation.return_value = {'Status': status, 'StandardOutputContent': text}
            self.assertEqual(cloud.receipt('command'), expected)


if __name__ == '__main__':
    unittest.main()
