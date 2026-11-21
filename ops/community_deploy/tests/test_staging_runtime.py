from copy import deepcopy
import json
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from ops.community_deploy import staging_runtime_app as app
from ops.community_deploy.staging_lifecycle import Policy, Refused, initial_state
from ops.community_deploy.tests import test_staging_lifecycle as fixture
from ops.community_deploy.tests import test_staging_request as request_fixture


class RuntimeTests(unittest.TestCase):
    def setUp(self):
        self.clock = fixture.Clock()
        self.config = dict(live_enabled=True, instance_id='i-1234567890abcdef0',
            policy_revision='c'*40, guard_revision='d'*40, guard_sha256='e'*64,
            max_lease_minutes=120, monthly_seconds=288000, region='ap-southeast-2',
            state_bucket='example-staging', state_key='staging/lifecycle.json',
            ssm_document_version='1', hostname='c-lara-2-staging.c-lara.org',
            health_url='https://c-lara-2-staging.c-lara.org/community-dictionaries/deployment-health/',
            function_name='staging-coordinator', live_alias_arn='arn:example:live',
            watchdog_alias_arn='arn:example:watchdog', schedule_name='staging-expiry',
            schedule_group='staging', credential_secret_arn='arn:example:secret',
            control_repository='example/staging-control', control_repository_id=321,
            allowed_sender_ids=[42])
        policy = Policy(self.config['instance_id'], 'c'*40, 'd'*40)
        self.store = fixture.Store(initial_state(policy, 'a'*40))
        self.store.value['watchdog_at'] = self.clock.now
        self.clients = {name:Mock() for name in ('s3','ssm','ec2','lambda','scheduler','secretsmanager')}
        for client in self.clients.values():
            client.meta.config = SimpleNamespace(retries={'total_max_attempts':1},
                                                  connect_timeout=2, read_timeout=3)
        self.clients['lambda'].get_function_concurrency.return_value = {'ReservedConcurrentExecutions':1}
        self.clients['lambda'].get_alias.side_effect = lambda **kw: {
            'AliasArn':self.config[kw['Name']+'_alias_arn'], 'FunctionVersion':'1'}
        self.clients['scheduler'].get_schedule.return_value = {'State':'ENABLED',
            'ScheduleExpression':'rate(1 minute)', 'Target':{'Arn':self.config['watchdog_alias_arn'],
                                                          'Input':'{"action":"tick"}'}}
        self.clients['ec2'].describe_instances.return_value = {'Reservations':[{'Instances':[{
            'InstanceId':self.config['instance_id'], 'State':{'Name':'stopped'},
            'Tags':[{'Key':'ClaraEnvironment','Value':'staging'},
                    {'Key':'ClaraGuardRevision','Value':'d'*40},
                    {'Key':'ClaraGuardSha256','Value':'e'*64}]}]}]}
        with patch.object(app, 'S3State', return_value=self.store):
            self.runtime = app.Runtime(self.config, self.clients, '1', clock=self.clock,
                                       source_read=lambda path: None, health_read=lambda *args: {})

    def test_only_independent_alias_updates_watchdog_heartbeat(self):
        self.clock.now += 30
        self.runtime.dispatch({'action':'tick'}, self.config['live_alias_arn'])
        self.assertEqual(self.store.value['watchdog_at'], self.clock.now-30)
        self.runtime.dispatch({'action':'tick'}, self.config['watchdog_alias_arn'])
        self.assertEqual(self.store.value['watchdog_at'], self.clock.now)
        with self.assertRaises(Refused):
            self.runtime.dispatch({'action':'open'}, self.config['watchdog_alias_arn'])
        with self.assertRaises(Refused):
            self.runtime.dispatch({'action':'status'}, 'unqualified-function')

    def test_actual_alias_schedule_tags_and_recent_heartbeat_are_checked(self):
        self.assertTrue(self.runtime.guards('d'*40))
        self.clock.now += 121
        with self.assertRaisesRegex(Refused,'independent_watchdog_heartbeat_missing'):
            self.runtime.guards('d'*40)
        self.runtime.dispatch({'action':'tick'}, self.config['watchdog_alias_arn'])
        self.assertTrue(self.runtime.guards('d'*40))
        self.clients['lambda'].get_function_concurrency.return_value = {'ReservedConcurrentExecutions':2}
        with self.assertRaisesRegex(Refused,'coordinator_not_serialized'):
            self.runtime.guards('d'*40)

    def test_original_issue_event_and_protected_ref_are_revalidated(self):
        source = request_fixture.StagingRequestTests(); source.setUp()
        environment = dict(source.environment, GITHUB_REF_PROTECTED='true')
        event = dict(action='open', event=source.event, environment=environment)
        with patch.object(self.runtime.coordinator, 'open', return_value={'phase':'starting'}) as opening:
            self.assertEqual(self.runtime.dispatch(event,self.config['live_alias_arn']),{'phase':'starting'})
            self.assertEqual(opening.call_args.args[0]['request_id'],'321:5')
            self.assertNotIn('verified',opening.call_args.args[0])
            environment['GITHUB_REF_PROTECTED']='false'
            with self.assertRaises(Refused):
                self.runtime.dispatch(event,self.config['live_alias_arn'])
            self.assertEqual(opening.call_count,1)

    def test_weighted_alias_cannot_bypass_published_guard_version(self):
        self.clients['lambda'].get_alias.side_effect=lambda **kw: {
            'AliasArn':self.config[kw['Name']+'_alias_arn'],'FunctionVersion':'1',
            'RoutingConfig':{'AdditionalVersionWeights':{'2':0.1}}}
        with self.assertRaisesRegex(Refused,'weighted_coordinator_alias_refused'):
            self.runtime.guards('d'*40)

    def test_unknown_commands_and_untrusted_overrides_are_refused(self):
        for event in [{'action':'reset'}, {'action':'close','lease_id':'x','instance_id':'production'},
                      {'action':'status','source_verified':True}]:
            with self.subTest(event=event),self.assertRaises(Refused):
                self.runtime.dispatch(event,self.config['live_alias_arn'])
        self.clients['ec2'].start_instances.assert_not_called()

    def test_readiness_is_bound_to_guard_hash_policy_lease_and_original_deadline(self):
        session={'lease_id':'lease-1','deadline':self.clock.now+900}
        self.store.value.update(active='321:5',requests={'321:5':session})
        self.clients['secretsmanager'].get_secret_value.return_value = {'SecretString':json.dumps({'seed':'x'*32})}
        data={'ready':True,'release':'a'*40,'maintenance':False,'staging_lease':{
            **session,'policy_revision':'c'*40,'guard_revision':'d'*40,'guard_sha256':'e'*64}}
        self.runtime.health_read=lambda *args:deepcopy(data)
        self.assertTrue(self.runtime.ready('a'*40,'lease-1'))
        data['staging_lease']['deadline']+=1
        self.assertFalse(self.runtime.ready('a'*40,'lease-1'))
        self.runtime.health_read=lambda *args:[]
        self.assertFalse(self.runtime.ready('a'*40,'lease-1'))

    def test_disabled_handler_never_constructs_aws_clients(self):
        with patch.dict(app.os.environ,{'CLARA_STAGING_CONFIG_JSON':'{"live_enabled":false}'}):
            result=app.handler({'action':'open'},SimpleNamespace())
        self.assertEqual(result['reason'],'live_staging_disabled')


if __name__=='__main__':
    unittest.main()
