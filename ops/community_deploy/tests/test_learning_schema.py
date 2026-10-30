import importlib.util
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]

def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module

helper = load('runner', ROOT / 'runner.py')
prepare = load('learning_schema', ROOT / 'prepare_learning_schema.py')
OLD, NEW = 'a'*40, 'b'*40


class FakeController:
    target = 'laptop'
    def __init__(self, path, failure=None, recover=True, paths=None):
        self.state = self.activity = Path(path)
        self.report = {}; self.current = OLD; self.calls = []
        self.failure, self.recover = failure, recover
        self.paths = paths if paths is not None else [prepare.MIGRATION, prepare.SCHEMA_SCRIPT]
    def clean(self): pass
    def head(self): return self.current
    def git(self, *args):
        self.calls.append(args)
        if args[0] == 'remote': return SimpleNamespace(stdout=helper.SOURCE)
        if args[0] == 'diff': return SimpleNamespace(stdout='\n'.join(self.paths))
        if args[0] == 'merge': self.current = NEW
        if args[0] == 'reset': self.current = OLD
        return SimpleNamespace(stdout='')
    def preflight(self): pass
    def port_open(self): return True
    def ready(self, sha):
        if sha == OLD and not self.recover and ('stop',) in self.calls: raise RuntimeError('recovery failed')
    def drain(self): pass
    def stop_server(self): self.calls.append(('stop',))
    def start_server(self): self.calls.append(('start',))
    def manage(self, *args, **kwargs):
        self.calls.append(args)
        if args[0] == self.failure: raise helper.Stop('deliberate failure')


class PreparationTests(unittest.TestCase):
    def run_case(self, **kwargs):
        with tempfile.TemporaryDirectory() as path:
            c = FakeController(path, **kwargs)
            result = prepare.prepare(c, helper, NEW, OLD, Path(path)/'receipt.json')
            return c, result, (Path(path)/'maintenance').exists()
    def test_only_reviewed_schema_prepared_then_service_started(self):
        c, r, gate = self.run_case()
        self.assertEqual(r['status'], 'prepared'); self.assertFalse(gate)
        shell = next(x for x in c.calls if x[0]=='shell')[-1]
        self.assertIn('quick_check', shell)
        self.assertIn('Other migrations are pending', shell)
        self.assertIn('Only the two new preference tables', shell)
        compile(shell, 'migration-command', 'exec')
    def test_unrelated_migrations_dependencies_and_workflows_refused_before_stop(self):
        for path in ['platform_server/projects/migrations/0099_bad.py', 'requirements.txt', '.github/workflows/ci.yml']:
            c, r, gate = self.run_case(paths=[path])
            self.assertEqual(r['status'], 'refused'); self.assertNotIn(('stop',), c.calls); self.assertFalse(gate)
    def test_migration_failure_restores_code_without_reversing_schema(self):
        c, r, gate = self.run_case(failure='shell')
        self.assertEqual(r['status'], 'recovered_previous_release'); self.assertEqual(c.current, OLD)
        self.assertFalse(gate)
        self.assertIn(('reset', '--keep', OLD), c.calls)
    def test_uncertain_recovery_retains_maintenance(self):
        c, r, gate = self.run_case(failure='shell', recover=False)
        self.assertEqual(r['status'], 'recovery_required'); self.assertTrue(gate)


if __name__ == '__main__': unittest.main()
