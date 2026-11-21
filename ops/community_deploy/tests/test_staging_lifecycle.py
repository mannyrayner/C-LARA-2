"""Fake clock/cloud failures exercise ownership, budgets and uncertain mutations."""
from copy import deepcopy
from datetime import datetime, timezone
import unittest
import uuid

from ops.community_deploy.staging_lifecycle import (
    Coordinator, Policy, Refused, StateUnavailable, initial_state, months)


BASE, CANDIDATE, CONTROL = 'a' * 40, 'b' * 40, 'c' * 40


class Clock:
    def __init__(self):
        self.now = int(datetime(2026, 11, 16, tzinfo=timezone.utc).timestamp())

    def __call__(self):
        return self.now


class Store:
    def __init__(self, state):
        self.value, self.token = deepcopy(state), 0
        self.read_error, self.write_error, self.after_write = False, False, None

    def read(self):
        if self.read_error:
            raise OSError('private provider diagnostic')
        return deepcopy(self.value), self.token

    def compare_and_swap(self, token, state):
        if self.write_error or token != self.token:
            raise OSError('private provider diagnostic')
        self.value, self.token = deepcopy(state), self.token + 1
        if self.after_write:
            self.after_write(state)
        return self.token


class Cloud:
    def __init__(self, store):
        self.store, self.status, self.calls = store, 'stopped', []
        self.guard_error = self.start_error = self.stop_error = self.deploy_error = False
        self.host_ready, self.result = False, None
        self.command_id = str(uuid.uuid4())

    def active(self):
        state = self.store.value
        return state['requests'][state['active']]

    def verify_guards(self, revision):
        self.calls.append('guards')
        if self.guard_error:
            raise Refused('shutdown_guards_not_verified')

    def instance_state(self):
        self.calls.append('describe')
        return self.status

    def start(self):
        self.calls.append('start')
        session = self.active()
        assert session['unknown']['start'] and session['phase'] == 'starting'
        assert session['reservation'] == months(session['armed_at'], session['deadline'])
        self.status = 'pending'
        if self.start_error:
            raise TimeoutError('private provider diagnostic')

    def stop(self):
        self.calls.append('stop')
        assert self.active()['unknown']['stop'] and self.active()['phase'] == 'stopping'
        self.status = 'stopping'
        if self.stop_error:
            raise TimeoutError('private provider diagnostic')

    def ready(self, expected, lease):
        assert expected == BASE and lease == self.active()['lease_id']
        return self.host_ready

    def deploy(self, commit, expected, lease):
        self.calls.append('deploy')
        assert self.active()['unknown']['deploy'] and lease == self.active()['lease_id']
        if self.deploy_error:
            raise TimeoutError('private provider diagnostic')
        return self.command_id

    def receipt(self, command_id):
        assert command_id == self.command_id
        return self.result


class LifecycleTests(unittest.TestCase):
    def setUp(self):
        self.clock = Clock()
        self.policy = Policy('i-1234567890abcdef0', CONTROL, 'd' * 40)
        self.store = Store(initial_state(self.policy, BASE))
        self.cloud = Cloud(self.store)
        self.verified = []
        def verify(request):
            self.verified.append(request)
            return True
        self.coordinator = Coordinator(self.policy, self.store, self.cloud, verify, self.clock)
        self.request = dict(request_id='123:1', commit=CANDIDATE, expected_staging=BASE,
                            lease_minutes=30, control_commit=CONTROL, run_id='456', run_attempt=1)

    def open(self, **changes):
        return self.coordinator.open(dict(self.request, **changes))

    def ready(self):
        lease = self.open()
        self.cloud.status, self.cloud.host_ready = 'running', True
        self.assertEqual(self.coordinator.tick()['phase'], 'ready')
        return lease['lease_id']

    def close(self, lease):
        self.coordinator.close(lease)
        self.cloud.status = 'stopped'
        return self.coordinator.tick()

    def test_reserves_before_start_and_duplicate_does_not_extend_or_restart(self):
        session = self.open()
        self.clock.now += 60
        again = self.open()
        self.assertEqual(again['deadline'], session['deadline'])
        self.assertEqual(again['lease_id'], session['lease_id'])
        self.assertEqual(self.cloud.calls.count('start'), 1)
        self.assertEqual(len(self.verified), 1)
        self.assertEqual(self.store.value['active'], '123:1')

    def test_closed_request_does_not_reopen_even_after_newer_session(self):
        lease = self.ready()
        self.clock.now += 45
        closed = self.close(lease)
        self.assertEqual(sum(closed['charges'].values()), 45)
        self.assertEqual(self.open()['phase'], 'closed')
        self.open(request_id='123:2')
        self.assertEqual(self.open()['phase'], 'closed')
        self.assertEqual(self.cloud.calls.count('start'), 2)

    def test_duplicate_id_with_changed_values_and_second_owner_are_refused(self):
        self.open()
        for changes in ({'lease_minutes': 60}, {'run_id': '457'}, {'request_id': '123:2'}):
            with self.subTest(changes=changes), self.assertRaises(Refused):
                self.open(**changes)
        self.assertEqual(self.cloud.calls.count('start'), 1)

    def test_no_start_with_unavailable_state_budget_guard_or_verification(self):
        self.store.read_error = True
        with self.assertRaisesRegex(StateUnavailable, 'state_read_unavailable'):
            self.open()
        self.store.read_error, self.store.write_error = False, True
        with self.assertRaisesRegex(StateUnavailable, 'state_write_unconfirmed'):
            self.open()
        self.store.write_error, self.cloud.guard_error = False, True
        with self.assertRaisesRegex(Refused, 'shutdown_guards_not_verified'):
            self.open()
        self.cloud.guard_error = False
        self.coordinator.verify_release = lambda request: False
        with self.assertRaisesRegex(Refused, 'release_not_verified'):
            self.open()
        self.assertNotIn('start', self.cloud.calls)
        self.assertIsNone(self.store.value['active'])

    def test_wrong_baseline_running_host_and_hostile_fields_refuse_before_start(self):
        for request in [dict(self.request, expected_staging='e' * 40),
                        dict(self.request, instance_id='i-production'),
                        dict(self.request, lease_minutes=True),
                        dict(self.request, lease_minutes=121),
                        dict(self.request, run_attempt=2), dict(self.request, commit='main')]:
            with self.subTest(request=request), self.assertRaises(Refused):
                self.coordinator.open(request)
        self.cloud.status = 'running'
        with self.assertRaisesRegex(Refused, 'instance_not_confirmed_stopped'):
            self.open()
        self.assertNotIn('start', self.cloud.calls)

    def test_start_timeout_retains_ownership_even_if_instance_appears_stopped(self):
        self.cloud.start_error = True
        with self.assertRaisesRegex(Refused, 'start_result_unknown'):
            self.open()
        self.cloud.status = 'stopped'
        with self.assertRaisesRegex(Refused, 'operator_reconciliation_required'):
            self.coordinator.tick()
        with self.assertRaises(Refused):
            self.open(request_id='123:2')
        self.assertEqual(self.cloud.calls.count('start'), 1)

    def test_unconfirmed_ack_write_never_retries_cloud_mutation(self):
        def interrupt(state):
            if state['requests'][state['active']]['phase'] == 'starting':
                self.store.write_error = True
        self.store.after_write = interrupt
        with self.assertRaises(StateUnavailable):
            self.open()
        self.store.write_error = False
        self.open()  # Same request only returns its existing unresolved state.
        self.assertEqual(self.cloud.calls.count('start'), 1)
        self.assertTrue(self.cloud.active()['unknown']['start'])

    def test_expiry_without_chat_stops_once_and_waits_for_confirmed_stop(self):
        session = self.open()
        self.cloud.status = 'running'
        self.clock.now = session['deadline']
        self.assertEqual(self.coordinator.tick()['phase'], 'stopping')
        self.coordinator.tick()
        self.assertIsNotNone(self.store.value['active'])
        self.assertEqual(self.cloud.calls.count('stop'), 1)
        self.cloud.status = 'stopped'
        self.clock.now += 20
        closed = self.coordinator.tick()
        self.assertEqual(sum(closed['charges'].values()), 1820)
        self.assertEqual(closed['phase'], 'closed')

    def test_delayed_old_close_cannot_stop_newer_session(self):
        first = self.ready()
        self.close(first)
        self.open(request_id='123:2')
        with self.assertRaisesRegex(Refused, 'stale_lease'):
            self.coordinator.close(first)
        self.assertEqual(self.cloud.calls.count('stop'), 1)

    def test_stop_timeout_does_not_release_budget_or_resubmit_stop(self):
        lease = self.ready()
        self.cloud.stop_error = True
        with self.assertRaisesRegex(Refused, 'stop_result_unknown'):
            self.coordinator.close(lease)
        self.cloud.status = 'stopped'
        with self.assertRaisesRegex(Refused, 'operator_reconciliation_required'):
            self.coordinator.tick()
        self.coordinator.close(lease)
        self.assertEqual(self.cloud.calls.count('stop'), 1)
        self.assertIsNotNone(self.store.value['active'])

    def test_original_deadline_survives_coordinator_restart(self):
        original = self.open()
        self.clock.now += 300
        restarted = Coordinator(self.policy, self.store, self.cloud, lambda r: True, self.clock)
        self.assertEqual(restarted.open(self.request)['deadline'], original['deadline'])
        self.assertEqual(self.cloud.calls.count('start'), 1)

    def test_deploy_once_and_verify_exact_terminal_receipt(self):
        lease = self.ready()
        command = self.coordinator.deploy(lease)
        self.assertEqual(command['command_id'], self.cloud.command_id)
        with self.assertRaises(Refused):
            self.coordinator.deploy(lease)
        self.cloud.result = dict(schema=1, target='staging', status='installed',
                                 commit=CANDIDATE, previous=BASE)
        self.assertEqual(self.coordinator.tick()['phase'], 'testing')
        self.assertEqual(self.store.value['baseline'], CANDIDATE)
        self.close(lease)
        self.assertFalse(self.store.value['recovery_required'])
        self.assertEqual(self.cloud.calls.count('deploy'), 1)

    def test_unknown_deploy_never_resubmits_and_next_start_is_blocked(self):
        lease = self.ready()
        self.cloud.deploy_error = True
        with self.assertRaisesRegex(Refused, 'deployment_submission_unknown'):
            self.coordinator.deploy(lease)
        with self.assertRaises(Refused):
            self.coordinator.deploy(lease)
        self.close(lease)
        self.assertTrue(self.store.value['recovery_required'])
        with self.assertRaisesRegex(Refused, 'operator_reconciliation_required'):
            self.open(request_id='123:2')
        self.assertEqual(self.cloud.calls.count('deploy'), 1)

    def test_stop_during_known_command_still_requires_checkout_reconciliation(self):
        lease = self.ready()
        self.coordinator.deploy(lease)
        self.close(lease)
        self.assertTrue(self.store.value['recovery_required'])
        with self.assertRaisesRegex(Refused, 'operator_reconciliation_required'):
            self.open(request_id='123:2')

    def test_recovered_candidate_is_failed_and_keeps_previous_baseline(self):
        lease = self.ready()
        self.coordinator.deploy(lease)
        self.cloud.result = dict(schema=1, target='staging', status='recovered_previous_release',
                                 commit=CANDIDATE, previous=BASE)
        result = self.coordinator.tick()
        self.assertEqual(result['phase'], 'stopping')
        self.assertEqual(result['outcome'], 'recovered_previous_release')
        self.assertEqual(self.store.value['baseline'], BASE)

    def test_wrong_receipt_requires_recovery_even_after_confirmed_stop(self):
        lease = self.ready()
        self.coordinator.deploy(lease)
        self.cloud.result = dict(schema=1, target='aws', status='installed',
                                 commit=CANDIDATE, previous=BASE)
        self.assertEqual(self.coordinator.tick()['phase'], 'stopping')
        self.cloud.status = 'stopped'
        self.assertEqual(self.coordinator.tick()['outcome'], 'recovery_required')

    def test_month_boundary_reservation_and_actual_stop_accounting(self):
        self.policy = Policy(self.policy.instance_id, CONTROL, 'd' * 40, monthly_seconds=900)
        self.coordinator.policy = self.policy
        self.clock.now = int(datetime(2026, 11, 30, 23, 59, 30, tzinfo=timezone.utc).timestamp())
        lease = self.open(lease_minutes=15)
        self.assertEqual(lease['reservation'], {'2026-11': 30, '2026-12': 870})
        self.cloud.status, self.cloud.host_ready = 'running', True
        self.coordinator.tick()
        self.clock.now += 60
        closed = self.close(lease['lease_id'])
        self.assertEqual(closed['charges'], {'2026-11': 30, '2026-12': 30})
        with self.assertRaisesRegex(Refused, 'monthly_budget_exhausted'):
            self.open(request_id='123:2', lease_minutes=15)

    def test_clock_rollback_and_policy_replacement_fail_closed(self):
        self.open()
        self.clock.now -= 1
        with self.assertRaisesRegex(Refused, 'clock_moved_backwards'):
            self.coordinator.tick()
        self.clock.now += 1
        self.store.value['policy_revision'] = 'e' * 40
        with self.assertRaisesRegex(Refused, 'state_policy_mismatch'):
            self.coordinator.tick()

    def test_corrupt_settled_charges_cannot_reopen_budget(self):
        lease = self.ready()
        self.clock.now += 60
        self.close(lease)
        self.store.value['requests']['123:1']['charges'] = {}
        with self.assertRaisesRegex(Refused, 'invalid_actual_runtime'):
            self.open(request_id='123:2')
        self.assertEqual(self.cloud.calls.count('start'), 1)

    def test_expired_intent_write_does_not_start_or_submit_deployment(self):
        def expire(state):
            if self.cloud.active()['unknown']['start']:
                self.clock.now = self.cloud.active()['deadline']
        self.store.after_write = expire
        with self.assertRaisesRegex(Refused, 'session_expired_before_start'):
            self.open()
        self.assertNotIn('start', self.cloud.calls)


if __name__ == '__main__':
    unittest.main()
