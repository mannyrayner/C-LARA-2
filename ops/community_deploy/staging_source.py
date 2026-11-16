"""Independent source/main, ancestry, eligible-diff and latest-CI verification.

Only the fixed public source repository is queried. Incomplete comparisons and
API errors refuse admission; there is no fallback to an older successful run.
"""
import json
import gzip
import io
import urllib.request

try:
    from .staging_lifecycle import Refused, require, sha
    from .runner import blocked_paths
except ImportError:
    from staging_lifecycle import Refused, require, sha
    from runner import blocked_paths


SOURCE = 'mannyrayner/C-LARA-2'
PREFIX = '/repos/' + SOURCE


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


def read_json_response(response, limit):
    raw = response.read(limit + 1)
    require(len(raw) <= limit, 'source_response_too_large')
    if response.headers.get('Content-Encoding', '').lower() == 'gzip' or raw[:2] == b'\x1f\x8b':
        with gzip.GzipFile(fileobj=io.BytesIO(raw)) as stream:
            raw = stream.read(limit + 1)
    require(len(raw) <= limit, 'source_response_too_large')
    return json.loads(raw)


def fetch(path):
    require(path.startswith(PREFIX + '/'), 'fixed_source_repository_required')
    request = urllib.request.Request('https://api.github.com' + path, headers={
        'Accept': 'application/vnd.github+json', 'X-GitHub-Api-Version': '2022-11-28',
        'User-Agent': 'C-LARA-staging-verifier'})
    try:
        with urllib.request.build_opener(NoRedirect).open(request, timeout=5) as response:
            return read_json_response(response, 2_097_152)
    except Exception:
        raise Refused('source_api_unavailable_or_incomplete') from None


class SourceVerifier:
    def __init__(self, read=fetch):
        self.read, self.report = read, None

    def compare(self, base, candidate, complete=False):
        reply = self.read(PREFIX + '/compare/' + sha(base) + '...' + sha(candidate))
        require(type(reply) is dict and reply.get('status') in {'ahead', 'identical'} and
                reply.get('merge_base_commit', {}).get('sha') == base and
                type(reply.get('behind_by')) is int and reply['behind_by'] == 0,
                'source_not_forward_ancestry')
        if complete:
            require(type(reply.get('total_commits')) is int and
                    0 <= reply['total_commits'] <= 250 and
                    type(reply.get('commits')) is list and
                    len(reply['commits']) == reply['total_commits'] and
                    type(reply.get('files')) is list and len(reply['files']) < 300,
                    'source_comparison_truncated')
            paths = []
            for item in reply['files']:
                require(type(item) is dict and isinstance(item.get('filename'), str) and
                        0 < len(item['filename']) <= 1024, 'invalid_changed_path')
                paths.append(item['filename'])
                if item.get('status') == 'renamed':
                    require(isinstance(item.get('previous_filename'), str), 'rename_source_missing')
                    paths.append(item['previous_filename'])
            require(not blocked_paths(paths), 'source_diff_requires_operator_release')
            return paths
        return []

    def __call__(self, request):
        self.report = None
        candidate, baseline = sha(request['commit']), sha(request['expected_staging'])
        main = self.read(PREFIX + '/git/ref/heads/main')
        require(type(main) is dict and main.get('ref') == 'refs/heads/main' and
                main.get('object', {}).get('type') == 'commit', 'source_main_identity')
        main_sha = sha(main['object']['sha'])
        self.compare(candidate, main_sha)
        paths = self.compare(baseline, candidate, complete=True)
        result = self.read(PREFIX + '/actions/workflows/ci.yml/runs?head_sha=' + candidate +
                           '&branch=main&event=push&per_page=1')
        require(type(result) is dict and type(result.get('total_count')) is int and
                result['total_count'] >= 1 and type(result.get('workflow_runs')) is list and
                len(result['workflow_runs']) == 1, 'source_ci_missing')
        run = result['workflow_runs'][0]
        require(run.get('status') == 'completed' and run.get('conclusion') == 'success' and
                run.get('event') == 'push' and run.get('head_branch') == 'main' and
                run.get('head_sha') == candidate and run.get('path') == '.github/workflows/ci.yml' and
                run.get('repository', {}).get('full_name') == SOURCE and
                type(run.get('id')) is int and run['id'] > 0, 'latest_source_ci_not_verified')
        self.report = {'source_repository': SOURCE, 'candidate': candidate,
                       'expected': baseline, 'main_observed': main_sha,
                       'ci_run_id': run['id'], 'changed_paths': paths}
        return True
