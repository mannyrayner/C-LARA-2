"""Trusted live assembly. Disabled unless explicitly configured by the operator.

The live and watchdog aliases share ONE function/version/concurrency limit.
Only the watchdog alias can update the independent heartbeat. Original issue
events are validated again; no request supplies source-verification flags,
resource identities, commands, URLs, credentials or a reset operation.
"""
import base64
import hashlib
import hmac
import json
import os
import time
import urllib.request

try:
    from .staging_lifecycle import Coordinator, Policy, Refused, require
    from .staging_aws import FixedCloud, S3State
    from .staging_source import NoRedirect, SourceVerifier, read_json_response
    from .staging_request import validate
except ImportError:
    from staging_lifecycle import Coordinator, Policy, Refused, require
    from staging_aws import FixedCloud, S3State
    from staging_source import NoRedirect, SourceVerifier, read_json_response
    from staging_request import validate


def credentials(secret):
    require(type(secret) is dict and isinstance(secret.get('seed'), str) and
            len(secret['seed']) >= 24, 'staging_credential_seed_required')
    return {name: hmac.new(secret['seed'].encode(), name.encode(), hashlib.sha256).hexdigest()
            for name in ('basic_password', 'owner_password', 'other_password')}


def read_health(url, username, password):
    token = base64.b64encode((username + ':' + password).encode()).decode()
    request = urllib.request.Request(url, headers={'Authorization': 'Basic ' + token,
                                                  'Cache-Control': 'no-cache'})
    try:
        with urllib.request.build_opener(NoRedirect).open(request, timeout=5) as response:
            require(response.status == 200, 'readiness_unavailable')
            return read_json_response(response, 8192)
    except Exception:
        return {}


class Runtime:
    def __init__(self, config, clients, execution_version, clock=None, source_read=None, health_read=read_health):
        self.config, self.clients = config, clients
        require(isinstance(execution_version, str) and execution_version.isdigit(),
                'published_runtime_version_required')
        self.execution_version = execution_version
        self.clock = clock or (lambda: int(time.time()))
        require(config.get('live_enabled') is True, 'live_staging_disabled')
        self.policy = Policy(config['instance_id'], config['policy_revision'], config['guard_revision'],
                             max_lease_minutes=config['max_lease_minutes'],
                             monthly_seconds=config['monthly_seconds'])
        require(config['health_url'] == 'https://' + config['hostname'] +
                '/community-dictionaries/deployment-health/', 'fixed_readiness_url_required')
        self.store = S3State(clients['s3'], config['state_bucket'], config['state_key'])
        self.source = SourceVerifier(source_read) if source_read else SourceVerifier()
        self.health_read = health_read
        self.cloud = FixedCloud(clients['ec2'], clients['ssm'], config['instance_id'],
                                config['ssm_document_version'], self.guards, self.ready)
        self.coordinator = Coordinator(self.policy, self.store, self.cloud, self.source, self.clock)

    def guards(self, revision):
        cfg = self.config
        reply = self.clients['lambda'].get_function_concurrency(FunctionName=cfg['function_name'])
        require(reply.get('ReservedConcurrentExecutions') == 1, 'coordinator_not_serialized')
        versions = []
        for name in ('live', 'watchdog'):
            alias = self.clients['lambda'].get_alias(FunctionName=cfg['function_name'], Name=name)
            require(alias.get('AliasArn') == cfg[name + '_alias_arn'], 'coordinator_alias_mismatch')
            require(not alias.get('RoutingConfig', {}).get('AdditionalVersionWeights'),
                    'weighted_coordinator_alias_refused')
            versions.append(alias.get('FunctionVersion'))
        require(versions[0] == versions[1] == self.execution_version,
                'coordinator_alias_versions_differ')
        schedule = self.clients['scheduler'].get_schedule(Name=cfg['schedule_name'],
                                                           GroupName=cfg['schedule_group'])
        require(schedule.get('State') == 'ENABLED' and
                schedule.get('ScheduleExpression') == 'rate(1 minute)' and
                schedule.get('Target', {}).get('Arn') == cfg['watchdog_alias_arn'] and
                json.loads(schedule['Target']['Input']) == {'action': 'tick'},
                'independent_watchdog_not_verified')
        rows = self.clients['ec2'].describe_instances(InstanceIds=[cfg['instance_id']])
        items = [item for group in rows.get('Reservations', []) for item in group.get('Instances', [])]
        require(len(items) == 1 and items[0].get('InstanceId') == cfg['instance_id'],
                'staging_instance_not_verified')
        tags = {item['Key']: item['Value'] for item in items[0].get('Tags', [])}
        require(tags.get('ClaraEnvironment') == 'staging' and
                tags.get('ClaraGuardRevision') == revision and
                tags.get('ClaraGuardSha256') == cfg['guard_sha256'], 'installed_guard_not_attested')
        state, _ = self.store.read()
        heartbeat = state.get('watchdog_at', 0)
        require(type(heartbeat) is int and 0 <= self.clock() - heartbeat <= 120,
                'independent_watchdog_heartbeat_missing')
        return True

    def ready(self, expected, lease_id):
        cfg = self.config
        state, _ = self.store.read()
        session = state.get('requests', {}).get(state.get('active'))
        require(type(session) is dict and session.get('lease_id') == lease_id,
                'readiness_lease_mismatch')
        reply = self.clients['secretsmanager'].get_secret_value(SecretId=cfg['credential_secret_arn'])
        secret = json.loads(reply['SecretString'])
        data = self.health_read(cfg['health_url'], 'pilot', credentials(secret)['basic_password'])
        if type(data) is not dict:
            return False
        marker = data.get('staging_lease')
        return (data.get('ready') is True and data.get('release') == expected and
                data.get('maintenance') is False and type(marker) is dict and
                marker.get('lease_id') == lease_id and marker.get('deadline') == session['deadline'] and
                marker.get('policy_revision') == self.policy.revision and
                marker.get('guard_revision') == self.policy.guard_revision and
                marker.get('guard_sha256') == cfg['guard_sha256'])

    def dispatch(self, event, invoked_arn):
        require(type(event) is dict and isinstance(event.get('action'), str), 'invalid_runtime_request')
        cfg, action = self.config, event['action']
        require(invoked_arn in {cfg['live_alias_arn'], cfg['watchdog_alias_arn']},
                'qualified_coordinator_alias_required')
        watchdog = invoked_arn == cfg['watchdog_alias_arn']
        if watchdog:
            require(event == {'action': 'tick'}, 'watchdog_tick_only')
            state, token, now = self.coordinator.load()
            state['watchdog_at'] = now
            self.coordinator.save(state, token, now)
            result=self.coordinator.tick()
            require(not (result.get('phase')=='stopping' and
                         now-result.get('stop_requested_at',now)>120),'stop_confirmation_overdue')
            return result
        if action == 'open':
            require(set(event) == {'action', 'event', 'environment'}, 'runtime_request_fields')
            environment = event['environment']
            require(type(environment) is dict and environment.get('GITHUB_REF_PROTECTED') == 'true',
                    'protected_control_ref_required')
            policy = dict(schema=1, mode='dry_run', repository=cfg['control_repository'],
                          repository_id=cfg['control_repository_id'], default_branch='main',
                          allowed_sender_ids=cfg['allowed_sender_ids'],
                          max_lease_minutes=self.policy.max_lease_minutes)
            request = validate(event['event'], policy, environment)
            normalized = {key: request[key] for key in
                ('request_id', 'commit', 'expected_staging', 'lease_minutes',
                 'control_commit', 'run_id', 'run_attempt')}
            return self.coordinator.open(normalized)
        if action in {'deploy', 'close'}:
            require(set(event) == {'action', 'lease_id'}, 'runtime_request_fields')
            return getattr(self.coordinator, action)(event['lease_id'])
        require(action in {'tick', 'status'} and event == {'action': action}, 'runtime_action_not_allowed')
        if action == 'tick':
            return self.coordinator.tick()
        state, _, _ = self.coordinator.load()
        return {'active': state['active'], 'baseline': state['baseline'],
                'recovery_required': state['recovery_required']}


def handler(event, context):
    try:
        config = json.loads(os.environ.get('CLARA_STAGING_CONFIG_JSON', '{}'))
        require(config.get('live_enabled') is True, 'live_staging_disabled')
        import boto3
        from botocore.config import Config
        client_config = Config(connect_timeout=2, read_timeout=3,
                               retries={'total_max_attempts': 1})
        clients = {name: boto3.client(name, region_name=config['region'], config=client_config)
                   for name in ('s3', 'ec2', 'ssm', 'lambda', 'scheduler', 'secretsmanager')}
        runtime = Runtime(config, clients, context.function_version)
        result = runtime.dispatch(event, context.invoked_function_arn)
        return {'schema': 1, 'target': 'staging', 'outcome': 'processed', 'result': result}
    except Refused as error:
        if (getattr(context,'invoked_function_arn','').endswith(':watchdog') and
                str(error)!='live_staging_disabled'):
            raise RuntimeError('staging_watchdog_needs_operator') from None
        return {'schema': 1, 'target': 'staging', 'outcome': 'refused', 'reason': str(error)}
    except Exception:
        if getattr(context,'invoked_function_arn','').endswith(':watchdog'):
            raise RuntimeError('staging_watchdog_unavailable') from None
        return {'schema': 1, 'target': 'staging', 'outcome': 'refused',
                'reason': 'runtime_verification_unavailable'}
