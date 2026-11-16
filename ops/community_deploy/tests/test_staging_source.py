from copy import deepcopy
import unittest
import gzip
import io
from types import SimpleNamespace

from ops.community_deploy.staging_lifecycle import Refused
from ops.community_deploy.staging_source import PREFIX, SourceVerifier, read_json_response


class SourceTests(unittest.TestCase):
    def setUp(self):
        self.base, self.candidate, self.main = 'a' * 40, 'b' * 40, 'c' * 40
        self.compare_main = dict(status='ahead', merge_base_commit={'sha': self.candidate}, behind_by=0)
        self.diff = dict(status='ahead', merge_base_commit={'sha': self.base}, behind_by=0,
                         total_commits=1, commits=[{'sha': self.candidate}],
                         files=[{'filename': 'platform_server/community_dictionary/templates/about.html',
                                 'status': 'modified'}])
        self.run = dict(id=12, status='completed', conclusion='success', event='push',
                        head_branch='main', head_sha=self.candidate, path='.github/workflows/ci.yml',
                        repository={'full_name': 'mannyrayner/C-LARA-2'})
        self.calls = []
        def read(path):
            self.calls.append(path)
            if path.endswith('/git/ref/heads/main'):
                return {'ref': 'refs/heads/main', 'object': {'sha': self.main, 'type': 'commit'}}
            if path.endswith(self.candidate + '...' + self.main):
                return deepcopy(self.compare_main)
            if '/compare/' in path:
                return deepcopy(self.diff)
            return {'total_count': 1, 'workflow_runs': [deepcopy(self.run)]}
        self.verifier = SourceVerifier(read)
        self.request = dict(commit=self.candidate, expected_staging=self.base)

    def test_candidate_and_main_are_pinned_and_exact_ci_is_recorded(self):
        self.assertTrue(self.verifier(self.request))
        self.assertEqual(self.verifier.report['ci_run_id'], 12)
        self.assertEqual(self.verifier.report['main_observed'], self.main)
        self.assertTrue(all(p.startswith(PREFIX + '/') for p in self.calls))

    def test_latest_failure_wrong_sha_workflow_or_repository_refuses(self):
        for field, value in [('conclusion', 'failure'), ('status', 'in_progress'),
                             ('event', 'pull_request'), ('head_sha', self.base),
                             ('path', '.github/workflows/other.yml'),
                             ('repository', {'full_name': 'other/repo'})]:
            old = deepcopy(self.run)
            self.run[field] = value
            with self.subTest(field=field), self.assertRaises(Refused):
                self.verifier(self.request)
            self.assertIsNone(self.verifier.report)
            self.run = old

    def test_diverged_truncated_and_renamed_controller_paths_refuse(self):
        for changes in [{'status': 'diverged'}, {'total_commits': 251},
                        {'files': [{'filename': 'a'}] * 300},
                        {'files': [{'filename': 'safe.txt', 'status': 'renamed',
                                    'previous_filename': 'ops/community_deploy/runner.py'}]},
                        {'files': [{'filename': 'safe.txt', 'status': 'renamed'}]}]:
            old = deepcopy(self.diff)
            self.diff.update(changes)
            with self.subTest(changes=changes), self.assertRaises(Refused):
                self.verifier(self.request)
            self.diff = old

    def test_unavailable_api_has_no_old_success_fallback(self):
        self.assertTrue(self.verifier(self.request))
        self.verifier.read = lambda path: (_ for _ in ()).throw(Refused('source_api_unavailable'))
        with self.assertRaises(Refused):
            self.verifier(self.request)
        self.assertIsNone(self.verifier.report)

    def test_compressed_json_is_decoded_with_a_decompressed_size_bound(self):
        for raw in [b'{"ok":true}', gzip.compress(b'{"ok":true}')]:
            stream=io.BytesIO(raw)
            response=SimpleNamespace(read=stream.read,headers={})
            self.assertEqual(read_json_response(response,100),{'ok':True})
        stream=io.BytesIO(gzip.compress(b' '*10000))
        with self.assertRaises(Refused):
            read_json_response(SimpleNamespace(read=stream.read,headers={}),100)


if __name__ == '__main__':
    unittest.main()
