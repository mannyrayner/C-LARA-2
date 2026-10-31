#!/usr/bin/env python3
"""Explicit one-time preparation for migration 0027; never called by Actions/SSM.

Reuses the installed trusted controller's host identities, gate, drain, process
management and recovery. Does not change that controller, its policy, IAM or CI.
The only permitted migration adds a Contribution kind choice. It emits no
database schema SQL and does not rewrite existing content. Run manually from the host runbook.
"""
import argparse
import importlib.util
from pathlib import Path
import sys

MIGRATION = 'platform_server/community_dictionary/migrations/0027_sentence_forms.py'
SCHEMA_SCRIPT = 'ops/community_deploy/prepare_forms_schema.py'
SCHEMA_TEST = 'ops/community_deploy/tests/test_forms_schema.py'
# Exact reviewed choice-only migration; no data or column type changes.
MIGRATION_SHA256 = 'e74257f6da786319d87e8edaaff4183778757af1563d1bea3fb2d45d64b83310'


def migration_code(backup_dir, backend):
    # Arguments are Python literals in an argv element, never shell text.
    return f'''
import hashlib, sqlite3
from datetime import datetime, timezone
from pathlib import Path
from django.conf import settings
from django.core.management import call_command
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.db.migrations.operations.fields import AlterField
expected_backend = {backend!r}
if connection.vendor != expected_backend:
    raise RuntimeError('Unexpected database backend')
path = settings.BASE_DIR / 'community_dictionary/migrations/0027_sentence_forms.py'
if hashlib.sha256(path.read_bytes().replace(bytes([13,10]), bytes([10]))).hexdigest() != {MIGRATION_SHA256!r}:
    raise RuntimeError('Migration differs from reviewed content')
executor = MigrationExecutor(connection)
target = ('community_dictionary', '0027_sentence_forms')
node = executor.loader.disk_migrations[target]
if (len(node.operations) != 1 or type(node.operations[0]) is not AlterField
        or node.operations[0].model_name != 'contribution' or node.operations[0].name != 'kind'):
    raise RuntimeError('Only the reviewed contribution-kind choice change is authorized')
plan = executor.migration_plan(executor.loader.graph.leaf_nodes())
if any(backwards or (m.app_label, m.name) != target for m, backwards in plan):
    raise RuntimeError('Other migrations are pending; stop and inspect')
if connection.vendor == 'sqlite':
    root = Path({str(backup_dir)!r})
    root.mkdir(mode=0o700, parents=True, exist_ok=True)
    name = root / ('before-forms-' + datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S-%f') + '.sqlite3')
    with sqlite3.connect(str(connection.settings_dict['NAME'])) as src, sqlite3.connect(str(name)) as dst:
        src.backup(dst)
        if dst.execute('PRAGMA quick_check').fetchall() != [('ok',)]:
            raise RuntimeError('Database backup verification failed')
    name.chmod(0o600)
    print('Verified SQLite backup:', name)
call_command('migrate', 'community_dictionary', '0027_sentence_forms', interactive=False)
print('Sentence-form metadata is ready. Existing dictionary content was not rewritten.')
'''


def prepare(c, helper, commit, expected, receipt):
    commit, expected = helper.sha(commit), helper.sha(expected)
    c.report.update(commit=commit, previous=expected, status='checking', operation='forms-schema-0027')
    stopped, owns_gate = False, False
    gate = c.activity / 'maintenance'
    with helper.locked(c.state):
        try:
            c.clean()
            if c.head() != expected: raise helper.Stop('installed_commit_does_not_match_request')
            if c.git('remote', 'get-url', 'origin').stdout.strip().rstrip('/').removesuffix('.git') != helper.SOURCE.removesuffix('.git'):
                raise helper.Stop('unexpected_origin')
            c.git('fetch', '--no-tags', 'origin', 'main')
            c.git('merge-base', '--is-ancestor', commit, 'FETCH_HEAD')
            c.git('merge-base', '--is-ancestor', expected, commit)
            paths = c.git('diff', '--no-renames', '--name-only', expected, commit).stdout.splitlines()
            if set(helper.blocked_paths(paths)) - {MIGRATION, SCHEMA_SCRIPT, SCHEMA_TEST}:
                raise helper.Stop('unreviewed_schema_dependencies_or_controller_change')
            c.preflight()
            if c.target == 'aws' or c.port_open(): c.ready(expected)
            with gate.open('x', encoding='utf-8') as stream: stream.write(commit + '\n')
            owns_gate = True
            c.drain()
            stopped = True
            c.stop_server()
            c.clean()
            if c.head() != expected: raise helper.Stop('checkout_changed_during_preparation')
            c.git('merge', '--ff-only', commit)
            c.manage('shell', '-v', '0', '-c', migration_code(c.state / 'backups',
                'sqlite' if c.target == 'laptop' else 'postgresql'))
            c.preflight()
            c.manage('collectstatic', '--noinput', static=True)
            c.start_server(); c.ready(commit)
            c.report['status'] = 'prepared'
        except BaseException as exc:
            c.report['reason'] = str(exc) if isinstance(exc, helper.Stop) else 'schema_preparation_failed'
            c.report['status'] = 'refused'
            if stopped:
                c.report['status'] = 'recovery_required'
                try:
                    c.stop_server(); c.clean()
                    if c.head() not in {commit, expected}: raise helper.Stop('unexpected_checkout_during_recovery')
                    if c.head() != expected: c.git('reset', '--keep', expected)
                    # The added choice is compatible with old code. Never reverse migrations.
                    c.manage('collectstatic', '--noinput', static=True)
                    c.start_server(); c.ready(expected)
                    c.report['status'] = 'recovered_previous_release'
                except BaseException:
                    c.report['status'] = 'recovery_required'
        finally:
            if owns_gate and c.report['status'] != 'recovery_required': gate.unlink(missing_ok=True)
            c.report['finished'] = helper.timestamp()
            helper.atomic_json(receipt, c.report)
    return c.report


def main():
    import json
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--controller', required=True, help='Installed trusted runner.py, outside the app checkout')
    p.add_argument('--config', required=True)
    p.add_argument('--commit', required=True, help='Exact reviewed schema-preparation commit from the runbook')
    p.add_argument('--expected', required=True)
    args = p.parse_args()
    path = Path(args.controller).resolve()
    spec = importlib.util.spec_from_file_location('installed_clara_controller', path)
    helper = importlib.util.module_from_spec(spec); spec.loader.exec_module(helper)
    c = helper.Controller(args.config)
    if path.is_relative_to(c.repo): raise SystemExit('Use the installed controller outside the application checkout.')
    result = prepare(c, helper, args.commit, args.expected, c.state / 'forms-schema-receipt.json')
    print(json.dumps(result))
    if result['status'] != 'prepared':
        print('Inspect the private controller log:', c.log)
        raise SystemExit(1)


if __name__ == '__main__': main()
