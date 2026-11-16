"""Offline integration boundaries: cleanup, bootstrap and reproducible packages."""
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock
from unittest.mock import patch
from types import SimpleNamespace
import stat
import zipfile

from ops.community_deploy import package_staging, staging_initialize, staging_job, staging_operator, staging_fault
from ops.community_deploy.staging_lifecycle import Refused


class JobTests(unittest.TestCase):
    def run_job(self, phases, browser=None, keep_open=False):
        self.calls=[];clock=[100]
        def invoke(**kwargs):
            self.calls.append(json.loads(kwargs['Payload']))
            value=phases.pop(0)
            if isinstance(value, Exception):raise value
            return {'Payload':io.BytesIO(json.dumps({'outcome':'processed','result':value}).encode())}
        client=Mock();client.invoke.side_effect=invoke
        def sleep(seconds):clock[0]+=seconds
        return staging_job.execute(client,'fixed-alias',{}, {},
            browser or (lambda _: {'outcome':'passed'}),clock=lambda:clock[0],sleep=sleep,
            keep_open=keep_open)

    def session(self, phase, **extra):
        return dict(phase=phase,lease_id='one-lease',deadline=1000,commit='a'*40,
                    request_id='321:5',**extra)

    def test_success_checks_browser_then_confirms_stop(self):
        result=self.run_job([self.session('starting'),self.session('ready'),
            self.session('deploying'),self.session('testing',outcome='installed'),
            self.session('stopping'),self.session('closed')])
        self.assertEqual(result['outcome'],'passed');self.assertTrue(result['stop_confirmed'])
        self.assertEqual([c['action'] for c in self.calls],['open','tick','deploy','tick','close','tick'])

    def test_browser_failure_still_stops_and_uncertain_stop_fails(self):
        for terminal in [self.session('closed'),TimeoutError('unknown stop')]:
            result=self.run_job([self.session('ready'),self.session('testing',outcome='installed'),terminal],
                               browser=lambda _: {'outcome':'failed'})
            self.assertEqual(result['outcome'],'failed')
            self.assertEqual(self.calls[-1],{'action':'close','lease_id':'one-lease'})

    def test_recovered_release_is_failed_and_never_browser_passed(self):
        browser=Mock()
        result=self.run_job([self.session('ready'),self.session('testing',outcome='recovered_previous_release'),
                             self.session('closed')],browser)
        browser.assert_not_called();self.assertEqual(result['outcome'],'failed')

    def test_explicit_inspection_does_not_extend_original_deadline(self):
        result=self.run_job([self.session('ready'),self.session('testing',outcome='installed')],keep_open=True)
        self.assertTrue(result['session_left_open_until_original_deadline'])
        self.assertEqual(result['deadline'],1000)
        self.assertEqual([c['action'] for c in self.calls],['open','deploy'])


class InitializeTests(unittest.TestCase):
    def setUp(self):
        self.config=dict(baseline='a'*40,instance_id='i-1234567890abcdef0',policy_revision='c'*40,
                         guard_revision='d'*40,guard_sha256='e'*64,state_bucket='own-staging')
        self.clients={name:Mock() for name in ('ec2','s3')}
        self.host={'InstanceId':self.config['instance_id'],'State':{'Name':'stopped'},
            'Tags':[{'Key':'ClaraEnvironment','Value':'staging'},
                    {'Key':'ClaraGuardRevision','Value':'d'*40},{'Key':'ClaraGuardSha256','Value':'e'*64}]}
        self.clients['ec2'].describe_instances.return_value={'Reservations':[{'Instances':[self.host]}]}
        self.receipt=dict(instance_id=self.config['instance_id'],baseline='a'*40,
                          guard_sha256='e'*64,policy_revision='c'*40)
        self.clients['s3'].get_object.side_effect=lambda **_: {'Body':io.BytesIO(json.dumps(self.receipt).encode())}

    def test_create_only_after_verified_stopped_bootstrap(self):
        staging_initialize.initialize(self.config,self.clients,lambda _:True)
        request=self.clients['s3'].put_object.call_args.kwargs
        self.assertEqual(request['IfNoneMatch'],'*')
        state=json.loads(request['Body']);self.assertIsNone(state['active'])
        self.clients['ec2'].start_instances.assert_not_called()
        self.clients['s3'].put_object.side_effect=RuntimeError('already exists')
        with self.assertRaises(RuntimeError):staging_initialize.initialize(self.config,self.clients,lambda _:True)
        self.assertEqual(self.clients['s3'].put_object.call_count,2)

    def test_bad_source_running_host_or_receipt_cannot_initialize(self):
        with self.assertRaises(Refused):staging_initialize.initialize(self.config,self.clients,lambda _:False)
        self.host['State']['Name']='running'
        with self.assertRaises(Refused):staging_initialize.initialize(self.config,self.clients,lambda _:True)
        self.host['State']['Name']='stopped';self.receipt['baseline']='b'*40
        with self.assertRaises(Refused):staging_initialize.initialize(self.config,self.clients,lambda _:True)
        self.clients['s3'].put_object.assert_not_called()


class PackageTests(unittest.TestCase):
    def test_deterministic_disabled_packages_and_fixed_iam_boundaries(self):
        root=Path(__file__).resolve().parents[3]
        with tempfile.TemporaryDirectory() as temporary:
            first=Path(temporary)/'first';second=Path(temporary)/'second'
            one=package_staging.build(root,first,'a'*40,True)
            two=package_staging.build(root,second,'a'*40,True)
            self.assertEqual(one,two);self.assertFalse(one['live_enabled'])
            self.assertTrue(one['working_tree_unreviewed'])
            self.assertEqual((first/'runtime.zip').read_bytes(),(second/'runtime.zip').read_bytes())
            with zipfile.ZipFile(first/'host-tools.zip') as package:
                self.assertIn('runtime/manage.sh',package.namelist())
                self.assertIn('staging_bootstrap_host.py',package.namelist())
            self.assertTrue((first/'operator/staging_initialize.py').is_file())
            runtime=json.loads((first/'runtime.cfn.json').read_text())
            self.assertEqual(runtime['Parameters']['EnableLive']['Default'],'false')
            statements=runtime['Resources']['RequesterRole']['Properties']['Policies'][0]['PolicyDocument']['Statement']
            actions=[s['Action'] for s in statements]
            self.assertNotIn('ec2:StartInstances',actions);self.assertNotIn('ssm:SendCommand',actions)
            invoke=next(s for s in statements if s['Action']=='lambda:InvokeFunction')
            self.assertEqual(invoke['Resource'],{'Ref':'LiveAlias'})
            self.assertIn('${EnableLive}',runtime['Resources']['Version']['Properties']['Description']['Fn::Sub'])
            with self.assertRaises(ValueError):package_staging.build(root,first,'a'*40)

    def test_operator_inputs_require_reviewed_bundle_and_match_host(self):
        manifest=dict(source_revision='a'*40,working_tree_unreviewed=False,live_enabled=False,
                      host_code_key='staging/bootstrap/host-tools-'+'d'*64+'.zip',host_zip_sha256='d'*64,
                      guard_sha256='e'*64)
        args=[manifest,{'InstanceId':'i-1234567890abcdef0'},
              {'CredentialSecretArn':'own-secret','StateBucket':'own-bucket'},'b'*40,
              'operator@example.org','code-bucket']
        config,parameters=staging_operator.prepare(*args)
        self.assertEqual(config['instance_id'],args[1]['InstanceId'])
        self.assertEqual(config['baseline'],'b'*40)
        self.assertIn('sha256sum --check --status','\n'.join(parameters['commands']))
        self.assertNotIn('GetSecretValue','\n'.join(parameters['commands']))
        manifest['working_tree_unreviewed']=True
        with self.assertRaises(ValueError):staging_operator.prepare(*args)

    def test_fault_is_exact_candidate_expiring_and_consumed_before_recovery(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'fault.json'
            value=dict(candidate='b'*40,armed_at=100,deadline=700)
            path.write_text(json.dumps(value))
            owner=SimpleNamespace(st_uid=0,st_mode=stat.S_IFREG|0o600)
            with patch.object(Path,'lstat',return_value=owner):
                self.assertFalse(staging_fault.consume(path,'a'*40,200))
                self.assertTrue(staging_fault.consume(path,'b'*40,200))
                self.assertFalse(staging_fault.consume(path,'b'*40,200))
                self.assertEqual(len(list(Path(directory).glob('consumed-*.json'))),1)
                path.write_text(json.dumps(value))
                self.assertFalse(staging_fault.consume(path,'b'*40,701))
                self.assertFalse(path.exists())


