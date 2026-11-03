"""Measurement and provenance regression tests; no network or application state."""
import contextlib
import csv
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import development_log as log


class JournalTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.time = '2026-11-03T10:00:00+00:00'
        self.journal = log.Journal(self.root/'private', clock=lambda:self.time)
        self.feature = 'DEV-001'
        self.request()

    def request(self, feature=None, at=None, timing='unknown'):
        return self.journal.append(feature or self.feature, 'request', 'Requested feature.',
            actor='human', source='human_report', occurred_at=at, timing=timing,
            data={'title':'A useful change', 'category':'feature'})

    def metrics(self):
        return next(f['metrics'] for f in log.describe(self.journal.read())['features']
                    if f['feature_id'] == self.feature)

    def start(self, phase='assistant_response', **kwargs):
        return self.journal.start(self.feature, phase, 'Work starts.', **kwargs)['data']['session_id']

    def receipt(self, **changes):
        return dict(schema=1, target='laptop', status='installed', commit='a'*40, previous='b'*40,
                    started='2026-11-03T10:02:00Z', finished='2026-11-03T10:03:00Z', **changes)

    def workflow(self, attempt=1, conclusion='success'):
        return {'repository':{'full_name':'example/private-control'}, 'status':'completed',
            'id':123, 'run_attempt':attempt, 'path':'.github/workflows/aws.yml',
            'head_sha':'c'*40, 'conclusion':conclusion, 'run_started_at':'2026-11-03T10:02:00Z',
            'updated_at':'2026-11-04T09:00:00Z'}

    def jobs(self, attempt=1):
        return {'total_count':1,'jobs':[{'id':456, 'run_id':123,'run_attempt':attempt,
                'status':'completed','completed_at':'2026-11-03T10:04:00Z'}]}

    def test_thirty_and_forty_five_minute_responses_and_nested_tool(self):
        first = self.start(coverage='partial')
        self.time = '2026-11-03T10:10:00Z'
        tool = self.start('tool')
        self.time = '2026-11-03T10:20:00Z'
        self.journal.stop(self.feature, tool, 'Tests finished.')
        self.time = '2026-11-03T10:30:00Z'
        self.journal.stop(self.feature, first, 'Response checkpoint.')
        self.time = '2026-11-03T11:00:00Z'
        second = self.start()
        self.time = '2026-11-03T11:45:00Z'
        self.journal.stop(self.feature, second, 'Response checkpoint.')
        metrics = self.metrics()
        self.assertEqual(metrics['elapsed_seconds']['assistant_response'], 4500)
        self.assertEqual(metrics['elapsed_seconds']['tool'], 600)
        self.assertEqual(metrics['partial_sessions'], 1)
        self.assertIsNone(metrics['request_to_first_ready_seconds'])

    def test_open_and_unknown_end_never_count_overnight(self):
        session = self.start()
        self.time = '2026-11-04T10:00:00Z'
        self.assertEqual(self.metrics()['elapsed_seconds']['assistant_response'], 0)
        self.assertEqual(self.metrics()['open_sessions'], 1)
        with self.assertRaises(log.Invalid):
            self.start()
        self.journal.stop(self.feature, session, 'Interrupted; actual end unknown.', unknown=True)
        self.assertEqual(self.metrics()['unknown_ended_sessions'], 1)
        self.assertEqual(self.metrics()['elapsed_seconds']['assistant_response'], 0)
        self.start()

    def test_overlap_merged_within_and_across_features(self):
        one = self.start(at='2026-11-03T10:00:00Z')
        self.journal.stop(self.feature, one, 'One.', at='2026-11-03T10:30:00Z')
        two = self.start(at='2026-11-03T10:15:00Z')
        self.journal.stop(self.feature, two, 'Two.', at='2026-11-03T10:45:00Z')
        self.request('DEV-002')
        other = self.journal.start('DEV-002','assistant_response','Shared interval.',at='2026-11-03T10:30:00Z')
        self.journal.stop('DEV-002',other['data']['session_id'],'End.',at='2026-11-03T11:00:00Z')
        report = log.describe(self.journal.read())
        self.assertEqual(self.metrics()['elapsed_seconds']['assistant_response'],2700)
        self.assertEqual(report['global_elapsed_seconds']['assistant_response'],3600)

    def test_negative_naive_and_duplicate_stops_refused(self):
        with self.assertRaises(log.Invalid):
            self.start(at='2026-11-03T10:00:00')
        session = self.start()
        with self.assertRaises(log.Invalid):
            self.journal.stop(self.feature, session, 'Bad clock.', at='2026-11-03T09:59:00Z')
        self.journal.stop(self.feature, session, 'End.')
        with self.assertRaises(log.Invalid):
            self.journal.stop(self.feature, session, 'Duplicate.')

    def test_captured_clock_keeps_occurrence_separate_from_record_time(self):
        capture = {'recorded_at':'2026-11-03T09:45:00Z','note':'First observed checkpoint.'}
        session = self.journal.start(self.feature,'assistant_response','Partial.',coverage='partial',capture=capture)
        self.assertEqual(session['occurred_at'],'2026-11-03T09:45:00+00:00')
        self.assertEqual(session['recorded_at'],self.time)
        self.assertEqual(session['source'],'clock_checkpoint')
        self.assertEqual(session['evidence'],['sha256:'+log.digest(capture)])
        self.journal.stop(self.feature,session['data']['session_id'],'End.')
        self.assertEqual(self.metrics()['elapsed_seconds']['assistant_response'],900)

    def test_receipt_idempotence_whitelist_and_failure(self):
        receipt = self.receipt(stdout='private output', environment={'KEY':'secret'}, log_path='/private/log')
        first = self.journal.import_receipt(self.feature,receipt)
        self.time = '2026-11-04T10:00:00Z'
        self.assertEqual(first,self.journal.import_receipt(self.feature,receipt))
        self.assertEqual(len(self.journal.read()),2)
        self.assertNotIn('secret',json.dumps(first))
        self.assertNotIn('private output',json.dumps(first))
        self.assertEqual(first['data']['duration_seconds'],60)
        self.assertEqual(first['data']['commit'],'a'*40)
        failed = dict(receipt,status='recovered_previous_release',finished='2026-11-03T10:05:00Z')
        self.journal.import_receipt(self.feature,failed)
        self.assertEqual(self.metrics()['unsuccessful_installations'],1)
        self.assertFalse(any(e['kind']=='acceptance' for e in self.journal.read()))

    def test_workflow_completion_uses_jobs_not_updated_at(self):
        event = self.journal.import_workflow(self.feature,self.workflow(),'example/private-control')
        self.assertIsNone(event['occurred_at'])
        self.assertEqual(event['timing'],'unknown')
        other = self.journal.import_workflow(self.feature,self.workflow(2,'failure'),'example/private-control',self.jobs(2))
        self.assertEqual(other['occurred_at'],'2026-11-03T10:04:00+00:00')
        self.assertEqual(self.journal.import_workflow(self.feature,self.workflow(2,'failure'),
                         'example/private-control',self.jobs(2)),other)
        self.assertEqual(self.metrics()['unsuccessful_workflows'],1)
        self.assertFalse(any(e['kind'] in {'acceptance','installation_finished'} for e in self.journal.read()))

    def test_workflow_mismatched_and_paginated_evidence_refused(self):
        for jobs in [dict(self.jobs(),total_count=2), self.jobs(2), [], {'total_count':1,'jobs':[None]}]:
            with self.subTest(jobs=jobs), self.assertRaises(log.Invalid):
                self.journal.import_workflow(self.feature,self.workflow(),'example/private-control',jobs)
        with self.assertRaises(log.Invalid):
            self.journal.import_workflow(self.feature,self.workflow(),'other/repo',self.jobs())
        for value in ([], None):
            with self.assertRaises(log.Invalid):
                self.journal.import_receipt(self.feature,value)
            with self.assertRaises(log.Invalid):
                self.journal.import_workflow(self.feature,value,'example/private-control')

    def test_correction_preserves_original_file(self):
        original = self.journal.append(self.feature,'revision_requested','Incorrect note.',data={'target':'laptop'})
        path = self.journal.root/'events'/(original['event_id']+'.json')
        before = path.read_bytes()
        self.journal.append(self.feature,'void','Wrong feature; corrected.',data={'event_id':original['event_id']})
        self.assertEqual(path.read_bytes(),before)
        self.assertEqual(self.metrics()['revision_requests'],0)
        self.assertEqual(log.describe(self.journal.read())['voided_event_count'],1)
        with self.assertRaises(log.Invalid):
            self.journal.append(self.feature,'void','No such event.',data={'event_id':'missing'})

    def test_human_acceptance_not_implied_by_install_or_assistant(self):
        self.journal.import_receipt(self.feature,self.receipt())
        with self.assertRaises(log.Invalid):
            self.journal.append(self.feature,'acceptance','Seems fine.',data={'target':'laptop'})
        with self.assertRaises(log.Invalid):
            self.journal.append(self.feature,'feature_closed','Done.',actor='human',data={'outcome':'accepted'})
        self.journal.append(self.feature,'acceptance','User confirmed checks.',actor='human',source='human_report',
                            data={'target':'laptop','commit':'a'*40})
        self.journal.append(self.feature,'feature_closed','User accepted.',actor='human',data={'outcome':'accepted'})
        self.assertEqual(log.describe(self.journal.read())['features'][0]['status'],'accepted')

    def test_turnaround_requires_exact_endpoints(self):
        self.request('DEV-002','2026-11-03T10:00:00Z','reported_exact')
        self.request('DEV-003','2026-11-03T10:00:00Z','approximate')
        for feature in ['DEV-001','DEV-002','DEV-003']:
            self.journal.append(feature,'implementation_ready','Ready.',data={'commit':'a'*40},
                                occurred_at='2026-11-03T10:45:00Z',timing='observed')
        report = {f['feature_id']:f for f in log.describe(self.journal.read())['features']}
        self.assertEqual(report['DEV-002']['metrics']['request_to_first_ready_seconds'],2700)
        for feature in ['DEV-001','DEV-003']:
            self.assertIsNone(report[feature]['metrics']['request_to_first_ready_seconds'])

    def test_incomplete_and_abandoned_features_are_exported(self):
        self.request('DEV-002')
        self.journal.append('DEV-002','feature_closed','Scope changed.',data={'outcome':'abandoned'})
        report = log.export(self.journal,self.root/'reports')['summary']
        self.assertEqual(report['feature_count'],2)
        self.assertEqual(report['open_feature_count'],1)
        self.assertEqual({f['status'] for f in report['features']},{'open','abandoned'})

    def test_csv_formula_safety_unicode_and_raw_json(self):
        original = '=HYPERLINK("malicious") — français'
        self.journal.append(self.feature,'note',original)
        output = self.root/'reports'
        dataset = log.export(self.journal,output)
        with (output/'development-events.csv').open(encoding='utf-8-sig',newline='') as stream:
            rows = list(csv.DictReader(stream))
        note = next(row for row in rows if row['kind']=='note')
        self.assertEqual(note['summary'],"'"+original)
        self.assertEqual(next(e for e in dataset['events'] if e['kind']=='note')['summary'],original)
        for value in [' +formula','\tformula','@formula','-formula']:
            self.assertTrue(log.csv_safe(value).startswith("'"))

    def test_unknown_feature_unsafe_identifier_and_lock_refused(self):
        with self.assertRaises(log.Invalid):
            self.journal.append('MISSING','note','Not a feature.')
        with self.assertRaises(log.Invalid):
            self.request('../outside')
        lock = self.journal.root/'.write-lock'
        lock.mkdir()
        with self.assertRaises(log.Invalid):
            self.journal.append(self.feature,'note','Second writer.')
        lock.rmdir()
        self.assertEqual(len(self.journal.read()),1)

    def test_cli_round_trip_without_application_dependencies(self):
        with contextlib.redirect_stdout(io.StringIO()) as out:
            self.assertEqual(log.cli(['--store',str(self.journal.root),'summary']),0)
        self.assertEqual(json.loads(out.getvalue())['feature_count'],1)
        result = subprocess.run([sys.executable,str(Path(log.__file__)),'--store',str(self.journal.root),'check'],
                                capture_output=True,text=True,check=True)
        self.assertTrue(json.loads(result.stdout)['valid'])


if __name__=='__main__':
    unittest.main()
