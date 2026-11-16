"""Bounded staging sessions. Importing this module never contacts AWS.

The trusted integration supplies a release verifier, a conditional state store
and a fixed-target cloud adapter. There is deliberately no live issue trigger
or permissive default verifier here. Serialize ALL invocations with one
function-wide Lambda reserved concurrency; conditional writes provide a second
fence against stale writers. Unknown mutations require operator reconciliation.
"""
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import re
import uuid


class Refused(RuntimeError):
    """Stable reason, safe to retain without raw provider diagnostics."""


class StateUnavailable(Refused):
    pass


SHA = re.compile(r'[0-9a-f]{40}\Z')
INSTANCE = re.compile(r'i-(?:[0-9a-f]{8}|[0-9a-f]{17})\Z')
REQUEST = re.compile(r'[1-9][0-9]{0,18}:[1-9][0-9]{0,18}\Z')
PHASES = {'armed', 'starting', 'ready', 'deploying', 'testing', 'stopping', 'closed'}


def require(condition, reason):
    if not condition:
        raise Refused(reason)


def sha(value):
    require(isinstance(value, str) and SHA.fullmatch(value) and value != '0' * 40,
            'invalid_commit')
    return value


def seconds(value):
    require(type(value) is int and 0 <= value < 2**53, 'invalid_clock')
    return value


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False)


def months(start, end):
    """Split a conservative charged/reserved interval at UTC month boundaries."""
    require(seconds(end) >= seconds(start), 'invalid_interval')
    result = {}
    while start < end:
        date = datetime.fromtimestamp(start, timezone.utc)
        boundary = datetime(date.year + (date.month == 12), date.month % 12 + 1,
                            1, tzinfo=timezone.utc)
        finish = min(end, int(boundary.timestamp()))
        result[date.strftime('%Y-%m')] = finish - start
        start = finish
    return result


@dataclass(frozen=True)
class Policy:
    instance_id: str
    revision: str
    guard_revision: str
    max_lease_minutes: int = 120
    monthly_seconds: int = 80 * 3600
    max_requests: int = 4096

    def __post_init__(self):
        require(isinstance(self.instance_id, str) and INSTANCE.fullmatch(self.instance_id),
                'invalid_instance')
        sha(self.revision)
        sha(self.guard_revision)
        require(type(self.max_lease_minutes) is int and 15 <= self.max_lease_minutes <= 120,
                'invalid_lease_policy')
        require(type(self.monthly_seconds) is int and 900 <= self.monthly_seconds <= 80 * 3600,
                'invalid_budget_policy')
        require(type(self.max_requests) is int and 1 <= self.max_requests <= 4096,
                'invalid_request_retention')


def initial_state(policy, baseline):
    """Operator bootstrap only; missing live state is never initialized on admission."""
    return {'schema': 1, 'instance_id': policy.instance_id, 'policy_revision': policy.revision,
            'baseline': sha(baseline), 'revision': 0, 'last_clock': 0,
            'active': None, 'recovery_required': False, 'requests': {}}


class Coordinator:
    def __init__(self, policy, store, cloud, verify_release, clock):
        require(callable(verify_release) and callable(clock), 'trusted_verifier_required')
        self.policy, self.store, self.cloud = policy, store, cloud
        self.verify_release, self.clock = verify_release, clock

    def load(self):
        try:
            state, token = self.store.read()
            state = deepcopy(state)
        except Exception:
            raise StateUnavailable('state_read_unavailable') from None
        p = self.policy
        require(type(state) is dict and type(state.get('schema')) is int and state['schema'] == 1 and
                state.get('instance_id') == p.instance_id and
                state.get('policy_revision') == p.revision, 'state_policy_mismatch')
        sha(state.get('baseline'))
        require(type(state.get('revision')) is int and state['revision'] >= 0 and
                type(state.get('last_clock')) is int and
                type(state.get('recovery_required')) is bool and
                type(state.get('requests')) is dict and
                len(state['requests']) <= p.max_requests, 'invalid_state')
        active = state.get('active')
        require(active is None or active in state['requests'], 'invalid_active_session')
        for key, session in state['requests'].items():
            require(isinstance(key, str) and REQUEST.fullmatch(key) and
                    type(session) is dict and session.get('phase') in PHASES and
                    session.get('request_id') == key, 'invalid_session')
            require(isinstance(session.get('lease_id'), str) and
                    str(uuid.UUID(session['lease_id'])) == session['lease_id'], 'invalid_lease_id')
            require(type(session.get('unknown')) is dict and
                    set(session['unknown']) == {'start', 'stop', 'deploy'} and
                    all(type(v) is bool for v in session['unknown'].values()), 'invalid_operation_state')
            require(seconds(session.get('deadline')) > seconds(session.get('armed_at')) and
                    session['deadline'] - session['armed_at'] <= p.max_lease_minutes * 60,
                    'invalid_session_deadline')
            require(type(session.get('reservation')) is dict and
                    session['reservation'] == months(session['armed_at'], session['deadline']) and
                    type(session.get('charges')) is dict, 'invalid_session_accounting')
            require((session['phase'] == 'closed') == (key != active), 'invalid_session_ownership')
            for field in ('commit', 'expected_staging', 'control_commit'):
                sha(session.get(field))
            if session['phase'] == 'closed':
                require(session['charges'] == months(session['armed_at'],
                                                     seconds(session.get('stopped_observed_at'))),
                        'invalid_actual_runtime')
            else:
                require(session['charges'] == {}, 'active_runtime_already_settled')
            for ledger in (session['reservation'], session['charges']):
                require(all(isinstance(k, str) and re.fullmatch(r'[0-9]{4}-[0-9]{2}', k) and
                            type(v) is int and v >= 0 for k, v in ledger.items()), 'invalid_budget')
        now = seconds(self.clock())
        require(now >= state['last_clock'], 'clock_moved_backwards')
        return state, token, now

    def save(self, state, token, now):
        state['last_clock'] = now
        state['revision'] += 1
        try:
            return self.store.compare_and_swap(token, deepcopy(state))
        except Exception:
            # A failed/ambiguous write NEVER authorizes a following cloud mutation.
            raise StateUnavailable('state_write_unconfirmed') from None

    def active(self, state, lease_id=None):
        require(state['active'] is not None, 'no_active_session')
        session = state['requests'][state['active']]
        if lease_id is not None:
            require(session['lease_id'] == lease_id, 'stale_lease')
        return session

    def open(self, request):
        keys = {'request_id', 'commit', 'expected_staging', 'lease_minutes', 'control_commit',
                'run_id', 'run_attempt'}
        require(type(request) is dict and set(request) == keys, 'request_fields')
        require(isinstance(request['request_id'], str) and REQUEST.fullmatch(request['request_id']),
                'invalid_request_id')
        for key in ('commit', 'expected_staging', 'control_commit'):
            sha(request[key])
        require(type(request['lease_minutes']) is int and
                15 <= request['lease_minutes'] <= self.policy.max_lease_minutes, 'request_lease')
        require(type(request['run_attempt']) is int and request['run_attempt'] == 1 and
                isinstance(request['run_id'], str) and
                re.fullmatch(r'[1-9][0-9]{0,18}', request['run_id']), 'original_run_required')
        fingerprint = hashlib.sha256(canonical(request).encode()).hexdigest()
        state, token, now = self.load()
        old = state['requests'].get(request['request_id'])
        if old:
            require(old['fingerprint'] == fingerprint, 'request_id_reused_with_other_data')
            return deepcopy(old)  # Closed or expired requests never reopen or renew.
        require(not state['recovery_required'], 'operator_reconciliation_required')
        require(state['active'] is None, 'session_already_owned')
        require(len(state['requests']) < self.policy.max_requests, 'request_retention_full')
        require(request['expected_staging'] == state['baseline'], 'stale_expected_release')
        require(self.verify_release(deepcopy(request)) is True, 'release_not_verified')
        self.cloud.verify_guards(self.policy.guard_revision)
        require(self.cloud.instance_state() == 'stopped', 'instance_not_confirmed_stopped')
        now = seconds(self.clock())
        require(now >= state['last_clock'], 'clock_moved_backwards')
        deadline = now + request['lease_minutes'] * 60
        reservation = months(now, deadline)
        for month, amount in reservation.items():
            charged = sum(s['charges'].get(month, 0) for s in state['requests'].values())
            require(charged + amount <= self.policy.monthly_seconds, 'monthly_budget_exhausted')
        session = dict(deepcopy(request), fingerprint=fingerprint, lease_id=str(uuid.uuid4()),
                       armed_at=now, deadline=deadline, reservation=reservation, charges={},
                       phase='armed', command_id=None,
                       unknown={'start': False, 'stop': False, 'deploy': False},
                       stop_submitted=False, outcome=None)
        state['requests'][request['request_id']] = session
        state['active'] = request['request_id']
        token = self.save(state, token, now)  # Durable reservation precedes start intent.
        session['phase'], session['unknown']['start'] = 'starting', True
        token = self.save(state, token, now)
        require(seconds(self.clock()) < deadline, 'session_expired_before_start')
        try:
            self.cloud.start()
        except Exception:
            # Keep the durable unresolved intent. Never retry StartInstances.
            raise Refused('start_result_unknown') from None
        session['unknown']['start'] = False
        token = self.save(state, token, now)
        return deepcopy(session)

    def deploy(self, lease_id):
        state, token, now = self.load()
        session = self.active(state, lease_id)
        require(now < session['deadline'], 'session_expired')
        require(not state['recovery_required'] and not any(session['unknown'].values()),
                'operator_reconciliation_required')
        require(session['phase'] == 'ready' and session['command_id'] is None,
                'deployment_already_submitted_or_not_ready')
        session['phase'], session['unknown']['deploy'] = 'deploying', True
        token = self.save(state, token, now)
        require(seconds(self.clock()) < session['deadline'], 'session_expired_before_deploy')
        try:
            command_id = self.cloud.deploy(session['commit'], session['expected_staging'], lease_id)
            require(isinstance(command_id, str) and
                    str(uuid.UUID(command_id)) == command_id, 'invalid_command_id')
        except Exception:
            raise Refused('deployment_submission_unknown') from None
        session['command_id'], session['unknown']['deploy'] = command_id, False
        self.save(state, token, now)
        return deepcopy(session)

    def stop(self, state, token, now, reason):
        session = self.active(state)
        if session['phase'] == 'stopping':
            return deepcopy(session)  # No retries of an uncertain StopInstances.
        session['phase'], session['stop_reason'] = 'stopping', reason
        session['stop_requested_at'], session['unknown']['stop'] = now, True
        token = self.save(state, token, now)
        try:
            self.cloud.stop()
        except Exception:
            raise Refused('stop_result_unknown') from None
        session['unknown']['stop'], session['stop_submitted'] = False, True
        self.save(state, token, now)
        return deepcopy(session)

    def close(self, lease_id):
        state, token, now = self.load()
        self.active(state, lease_id)  # A delayed stop cannot target a newer lease.
        return self.stop(state, token, now, 'explicit_close')

    def tick(self):
        """One bounded reconciliation step; no polling runner is held idle."""
        state, token, now = self.load()
        if state['active'] is None:
            return {'phase': 'idle', 'recovery_required': state['recovery_required']}
        session = self.active(state)
        status = self.cloud.instance_state()
        if status == 'stopped':
            # Unresolved starts/stops might still complete late. Do not release
            # ownership based only on a stopped observation after an ambiguous API.
            require(not session['unknown']['start'] and not session['unknown']['stop'],
                    'operator_reconciliation_required')
            state['recovery_required'] |= (session['phase'] in {'armed', 'starting', 'deploying'} or
                                           session['unknown']['deploy'] or
                                           (session['command_id'] is not None and
                                            session['outcome'] is None))
            session['charges'] = months(session['armed_at'], now)
            session['stopped_observed_at'], session['phase'] = now, 'closed'
            session['outcome'] = ('recovery_required' if state['recovery_required'] else
                                  session['outcome'] or 'closed')
            state['active'] = None
            self.save(state, token, now)
            return deepcopy(session)
        if now >= session['deadline']:
            return self.stop(state, token, now, 'expired')
        if session['phase'] == 'stopping':
            return deepcopy(session)
        require(not any(session['unknown'].values()), 'operator_reconciliation_required')
        if status != 'running':
            return deepcopy(session)
        if session['phase'] == 'starting' and self.cloud.ready(session['expected_staging'],
                                                               session['lease_id']):
            session['phase'] = 'ready'
            self.save(state, token, now)
        elif session['phase'] == 'deploying':
            receipt = self.cloud.receipt(session['command_id'])
            if receipt is not None:
                valid = (type(receipt) is dict and receipt.get('schema') == 1 and
                         receipt.get('target') == 'staging' and
                         receipt.get('commit') == session['commit'] and
                         receipt.get('previous') == session['expected_staging'] and
                         receipt.get('status') in {'installed', 'refused', 'recovered_previous_release'})
                if not valid:
                    state['recovery_required'] = True
                    token = self.save(state, token, now)
                    return self.stop(state, token, now, 'unverified_deployment_outcome')
                session['outcome'] = receipt['status']
                state['baseline'] = (session['commit'] if receipt['status'] == 'installed' else
                                     session['expected_staging'])
                session['phase'] = 'testing'
                token = self.save(state, token, now)
                if receipt['status'] != 'installed':
                    return self.stop(state, token, now, 'deployment_failed')
        return deepcopy(session)
