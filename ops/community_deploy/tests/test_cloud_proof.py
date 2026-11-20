"""Deployment-proof selection with simulated GitHub data; never contacts AWS."""
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import cloud

CONTROL, EARLIER, COMMIT, PREVIOUS = (c * 40 for c in 'abcd')


def run(number, *, conclusion='success', control=CONTROL, **extra):
    return {'id':number, 'run_attempt':1, 'status':'completed', 'conclusion':conclusion,
        'event':'workflow_dispatch', 'head_branch':'main', 'head_sha':control,
        'path':'.github/workflows/laptop.yml', 'updated_at':datetime.now(timezone.utc).isoformat(), **extra}


class LaptopProofTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(); self.addCleanup(temp.cleanup)
        previous = Path.cwd(); os.chdir(temp.name); self.addCleanup(os.chdir, previous)
        self.addCleanup(patch.stopall)
        patch.dict(os.environ, GITHUB_REPOSITORY='owner/control', GITHUB_SHA=CONTROL).start()
        self.request = {'commit':COMMIT, 'expected_laptop':PREVIOUS}
        self.receipt = {'schema':1, 'status':'installed', 'target':'laptop', 'commit':COMMIT, 'previous':PREVIOUS}
        self.runs = [run(42)]
        self.jobs = {'total_count':0, 'jobs':[]}
        self.changed = None
        self.ancestor = True
        self.downloads = []
        self.api_calls = []
        patch.object(cloud, 'call', side_effect=self.api).start()
        patch.object(cloud.subprocess, 'run', side_effect=self.download).start()

    def api(self, args):
        self.assertEqual(args[:2], ['gh','api'], 'Proof must never send an AWS request')
        path = args[2]; self.api_calls.append(path)
        if '/actions/workflows/' in path:
            return {'workflow_runs':self.runs}
        if '/jobs?' in path:
            return self.jobs
        if '/compare/' in path:
            return {'behind_by':0 if self.ancestor else 1, 'merge_base_commit':{'sha':EARLIER}}
        if '/contents/' in path:
            name = path.split('/contents/')[1].split('?')[0]
            # Each proof-relevant file has an immutable, independently matched
            # blob. Any change at the current head must invalidate old proof.
            value = str(cloud.PROOF_FILES.index(name)+1) * 40
            if name == self.changed and path.endswith('ref='+CONTROL): value = 'f' * 40
            return {'sha':value}
        raise AssertionError('Unexpected API request: '+path)

    def download(self, args, **kwargs):
        self.assertEqual(args[:3], ['gh','run','download'])
        self.downloads.append(int(args[3]))
        directory = Path(args[args.index('--dir')+1]); directory.mkdir()
        (directory/'receipt.json').write_text(json.dumps(self.receipt))
        return SimpleNamespace(returncode=0)

    def test_latest_success_is_unchanged_and_no_extra_snapshot_calls(self):
        self.assertEqual(cloud.proof(self.request),42)
        self.assertEqual(self.downloads,[42])
        self.assertEqual(len(self.api_calls),1)

    def test_queued_cancelled_duplicates_use_the_first_real_success(self):
        self.runs = [run(44,conclusion='cancelled'),run(43,conclusion='cancelled'),run(42)]
        self.assertEqual(cloud.proof(self.request),42)
        self.assertEqual(self.downloads,[42])

    def test_cancellation_after_any_job_started_is_not_skipped(self):
        self.runs = [run(43,conclusion='cancelled'),run(42)]
        self.jobs = {'total_count':1, 'jobs':[{'conclusion':'cancelled','steps':[]}]}
        with self.assertRaises(cloud.Stop): cloud.proof(self.request)
        self.assertEqual(self.downloads,[])

    def test_cancelled_rerun_or_missing_attempt_metadata_is_not_skipped(self):
        for attempt in [2, None]:
            self.runs = [run(43,conclusion='cancelled',run_attempt=attempt),run(42)]
            with self.subTest(attempt=attempt), self.assertRaises(cloud.Stop): cloud.proof(self.request)
        self.assertEqual(self.downloads,[])

    def test_incomplete_cancellation_metadata_is_not_skipped(self):
        self.runs = [run(43,conclusion='cancelled'),run(42)]
        for jobs in [{}, {'jobs':[]}, {'total_count':0}, {'total_count':0,'jobs':[{}]}]:
            self.jobs=jobs
            with self.subTest(jobs=jobs), self.assertRaises(cloud.Stop): cloud.proof(self.request)
        self.assertEqual(self.downloads,[])

    def test_failure_in_progress_and_wrong_identity_never_fall_back(self):
        bad = [run(43,conclusion='failure'),run(43,conclusion=None,status='in_progress'),
               run(43,head_branch='other'),run(43,event='pull_request'),
               run(43,path='.github/workflows/other.yml')]
        for latest in bad:
            self.runs=[latest,run(42)]
            with self.subTest(latest=latest), self.assertRaises(cloud.Stop): cloud.proof(self.request)
        self.assertEqual(self.downloads,[])

    def test_a_real_failure_between_cancellations_and_success_still_blocks(self):
        self.runs=[run(44,conclusion='cancelled'),run(43,conclusion='failure'),run(42)]
        with self.assertRaises(cloud.Stop): cloud.proof(self.request)
        self.assertEqual(self.downloads,[])

    def test_helper_only_update_accepts_exact_unchanged_release_and_installer(self):
        self.runs=[run(43,conclusion='cancelled',control=EARLIER),run(42,control=EARLIER)]
        self.assertEqual(cloud.proof(self.request),42)
        self.assertEqual(self.downloads,[42])
        self.assertEqual(sum('/contents/' in path for path in self.api_calls),6, 'Immutable snapshots are cached')

    def test_changed_request_workflow_or_runner_requires_new_proof(self):
        self.runs=[run(42,control=EARLIER)]
        for name in cloud.PROOF_FILES:
            self.changed=name
            with self.subTest(name=name), self.assertRaises(cloud.Stop): cloud.proof(self.request)
        self.assertEqual(self.downloads,[])

    def test_unrelated_control_history_is_rejected(self):
        self.runs=[run(42,control=EARLIER)]; self.ancestor=False
        with self.assertRaises(cloud.Stop): cloud.proof(self.request)
        self.assertEqual(self.downloads,[])

    def test_stale_success_is_not_made_fresh_by_a_new_cancellation(self):
        self.runs=[run(43,conclusion='cancelled'),run(42,updated_at='2020-01-01T00:00:00Z')]
        with self.assertRaises(cloud.Stop): cloud.proof(self.request)
        self.assertEqual(self.downloads,[])

    def test_receipt_still_requires_exact_original_transition(self):
        for field,value in [('status','refused'),('target','aws'),('commit',PREVIOUS),('previous',COMMIT)]:
            with self.subTest(field=field), self.assertRaises(cloud.Stop):
                cloud.verify_receipt({**self.receipt,field:value},self.request)

    def test_all_queued_cancellations_or_no_runs_require_a_success(self):
        for runs in [[],[run(43,conclusion='cancelled')]]:
            self.runs=runs
            with self.subTest(runs=runs), self.assertRaises(cloud.Stop): cloud.proof(self.request)
        self.assertEqual(self.downloads,[])


if __name__ == '__main__':
    unittest.main()
