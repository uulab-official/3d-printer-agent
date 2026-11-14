"""Data selection, real-process ownership and installation diagnostics."""
import contextlib
import json
import os
from pathlib import Path
import subprocess
import sqlite3
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

from print_agent.runtime import (
    DataDirectoryInUse, DataDirectoryLease, diagnose, resolve_data_directory,
)


@contextlib.contextmanager
def working_directory(path):
    previous = Path.cwd()
    try:
        os.chdir(path)
        yield
    finally:
        os.chdir(previous)


class DataDirectoryTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.env = patch.dict(os.environ, {'PPA_DATA_DIR': '', 'XDG_DATA_HOME': '', 'LOCALAPPDATA': ''})
        self.env.start()
        self.addCleanup(self.env.stop)

    def test_explicit_path_precedes_environment_and_legacy_without_creating_it(self):
        (self.root / 'data').mkdir()
        (self.root / 'data' / 'history.sqlite3').write_bytes(b'preserve')
        with working_directory(self.root), patch.dict(os.environ, {'PPA_DATA_DIR': str(self.root / 'environment')}):
            result = resolve_data_directory(Path('선택한 작업 space'))
        self.assertEqual(result, {'path': str(self.root / '선택한 작업 space'), 'source': 'argument', 'legacy': False})
        self.assertFalse(Path(result['path']).exists())

    def test_nonempty_environment_path_precedes_legacy(self):
        (self.root / 'data').mkdir()
        (self.root / 'data' / 'history.sqlite3').touch()
        target = self.root / 'environment'
        with working_directory(self.root), patch.dict(os.environ, {'PPA_DATA_DIR': str(target)}):
            self.assertEqual(resolve_data_directory(), {'path': str(target), 'source': 'environment', 'legacy': False})

    def test_legacy_databases_are_adopted_without_rewriting_their_bytes(self):
        for filename in ('history.sqlite3', 'profile-workspaces.sqlite3'):
            with self.subTest(filename=filename), tempfile.TemporaryDirectory(dir=self.root) as temp:
                launch = Path(temp)
                legacy = launch / 'data'
                legacy.mkdir()
                sentinel = legacy / filename
                sentinel.write_bytes(b'unexamined legacy bytes')
                with working_directory(launch):
                    self.assertEqual(resolve_data_directory(), {'path': str(legacy), 'source': 'legacy', 'legacy': True})
                self.assertEqual(sentinel.read_bytes(), b'unexamined legacy bytes')

    def test_original_job_records_are_recognized_without_an_index(self):
        legacy = self.root / 'data'
        job = legacy / 'jobs' / ('a' * 32)
        job.mkdir(parents=True)
        (job / 'job.json').write_bytes(b'{"unfinished":')
        with working_directory(self.root):
            result = resolve_data_directory()
        self.assertEqual(result['source'], 'legacy')
        self.assertEqual(result['path'], str(legacy))
        self.assertEqual((job / 'job.json').read_bytes(), b'{"unfinished":')

    def test_empty_data_directory_does_not_hide_stable_user_storage(self):
        launches = [self.root / 'one', self.root / 'two']
        for launch in launches:
            (launch / 'data').mkdir(parents=True)
        with patch('print_agent.runtime.platform.system', return_value='Linux'), \
             patch.dict(os.environ, {'XDG_DATA_HOME': str(self.root / 'user-data'), 'PPA_DATA_DIR': '   '}):
            with working_directory(launches[0]):
                first = resolve_data_directory()
            with working_directory(launches[1]):
                second = resolve_data_directory()
        self.assertEqual(first, second)
        self.assertEqual(first, {'path': str(self.root / 'user-data' / '3d-printer-agent'), 'source': 'user_default', 'legacy': False})
        self.assertFalse(Path(first['path']).exists())

    def test_platform_defaults_do_not_depend_on_the_launch_directory(self):
        cases = [
            ('Darwin', {}, self.root / 'Library' / 'Application Support' / '3DPrinterAgent'),
            ('Windows', {'LOCALAPPDATA': str(self.root / 'local-apps')}, self.root / 'local-apps' / '3DPrinterAgent'),
            ('Windows', {}, self.root / 'AppData' / 'Local' / '3DPrinterAgent'),
            ('Linux', {'XDG_DATA_HOME': 'relative-is-ignored'}, self.root / '.local' / 'share' / '3d-printer-agent'),
        ]
        for system, environment, expected in cases:
            with self.subTest(system=system, environment=environment), working_directory(self.root), \
                 patch('print_agent.runtime.platform.system', return_value=system), \
                 patch('print_agent.runtime.Path.home', return_value=self.root), patch.dict(os.environ, environment):
                self.assertEqual(resolve_data_directory()['path'], str(expected))


class DirectoryLeaseTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name) / '작업 directory'

    def test_same_root_is_exclusive_and_release_keeps_existing_data_and_lock_file(self):
        self.root.mkdir()
        sentinel = self.root / 'keep.txt'
        sentinel.write_text('unchanged', encoding='utf-8')
        with DataDirectoryLease(self.root):
            lock = self.root / '.printer-agent.lock'
            before = (lock.stat().st_size, lock.stat().st_mtime_ns)
            with self.assertRaises(DataDirectoryInUse):
                with DataDirectoryLease(self.root / '..' / self.root.name):
                    self.fail('second owner was admitted')
            self.assertEqual((lock.stat().st_size, lock.stat().st_mtime_ns), before)
            self.assertEqual(sentinel.read_text(encoding='utf-8'), 'unchanged')
        self.assertTrue(lock.exists())
        self.assertEqual(lock.read_bytes(), b'\0')
        with DataDirectoryLease(self.root):
            self.assertEqual(sentinel.read_text(encoding='utf-8'), 'unchanged')

    def test_an_independent_process_is_rejected_until_the_owner_releases(self):
        code = '''
import sys
from pathlib import Path
from print_agent.runtime import DataDirectoryLease, DataDirectoryInUse
try:
    with DataDirectoryLease(Path(sys.argv[1])):
        print('acquired')
except DataDirectoryInUse:
    print('in_use')
'''
        with DataDirectoryLease(self.root):
            blocked = subprocess.run([sys.executable, '-c', code, str(self.root)], capture_output=True, text=True, timeout=15)
        released = subprocess.run([sys.executable, '-c', code, str(self.root)], capture_output=True, text=True, timeout=15)
        self.assertEqual(blocked.returncode, 0, blocked.stderr)
        self.assertEqual(blocked.stdout.strip(), 'in_use')
        self.assertEqual(released.returncode, 0, released.stderr)
        self.assertEqual(released.stdout.strip(), 'acquired')

    def test_process_termination_releases_ownership_without_deleting_the_lock(self):
        ready = Path(self.temporary.name) / 'ready'
        code = '''
import sys, time
from pathlib import Path
from print_agent.runtime import DataDirectoryLease
with DataDirectoryLease(Path(sys.argv[1])):
    Path(sys.argv[2]).write_text('ready', encoding='utf-8')
    time.sleep(30)
'''
        child = subprocess.Popen([sys.executable, '-c', code, str(self.root), str(ready)], stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        try:
            deadline = time.monotonic() + 10
            while not ready.exists() and child.poll() is None and time.monotonic() < deadline:
                time.sleep(0.02)
            self.assertTrue(ready.exists(), 'independent owner did not acquire its lease')
            with self.assertRaises(DataDirectoryInUse):
                with DataDirectoryLease(self.root):
                    self.fail('active owner was ignored')
        finally:
            if child.poll() is None:
                child.terminate()
            child.communicate(timeout=10)
        self.assertTrue((self.root / '.printer-agent.lock').exists())
        with DataDirectoryLease(self.root):
            pass

    def test_regular_file_data_path_is_not_modified(self):
        self.root.write_bytes(b'keep the file')
        with self.assertRaises((OSError, ValueError)):
            with DataDirectoryLease(self.root):
                self.fail('a regular file became a data directory')
        self.assertEqual(self.root.read_bytes(), b'keep the file')

    def test_nested_entry_on_the_same_lease_cannot_release_the_original_lock(self):
        lease = DataDirectoryLease(self.root)
        with lease:
            with self.assertRaises(RuntimeError):
                lease.__enter__()
            with self.assertRaises(DataDirectoryInUse):
                with DataDirectoryLease(self.root):
                    self.fail('nested entry released the first owner')
        with DataDirectoryLease(self.root):
            pass


class DiagnosticsTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)

    def test_storage_file_failure_is_reported_without_altering_it(self):
        path = self.root / 'file'
        path.write_bytes(b'do not change')
        report = diagnose(path)
        self.assertFalse(report['ready'])
        self.assertEqual(report['storage']['path'], str(path))
        self.assertFalse(next(check for check in report['checks'] if check['id'] == 'storage')['passed'])
        self.assertEqual(path.read_bytes(), b'do not change')

    def test_storage_probe_cleans_up_and_does_not_create_databases_or_lock(self):
        (self.root / 'original.json').write_text('preserve', encoding='utf-8')
        before = {path.name: path.read_bytes() for path in self.root.iterdir()}
        report = diagnose(self.root)
        after = {path.name: path.read_bytes() for path in self.root.iterdir()}
        self.assertTrue(report['ready'], report['checks'])
        self.assertEqual(before, after)

    def test_missing_data_directory_is_checked_without_creating_it(self):
        path = self.root / 'not-created' / 'nested'
        report = diagnose(path)
        self.assertTrue(report['ready'], report['checks'])
        self.assertFalse(path.exists())
        self.assertEqual(list(self.root.iterdir()), [])

    def test_failed_cad_import_is_caught_and_other_checks_continue(self):
        with patch.dict(sys.modules, {'cadquery': None}):
            report = diagnose(self.root)
        self.assertFalse(report['ready'])
        self.assertIsNone(report['cadquery'])
        checks = {check['id']: check for check in report['checks']}
        self.assertFalse(checks['cadquery']['passed'])
        self.assertTrue(checks['sqlite3']['passed'])
        self.assertTrue(checks['storage']['passed'])

    def test_failed_sqlite_import_does_not_escape_diagnostics(self):
        (self.root / 'history.sqlite3').touch()
        with patch.dict(sys.modules, {'sqlite3': None}):
            report = diagnose(self.root)
        self.assertFalse(report['ready'])
        checks = {check['id']: check for check in report['checks']}
        self.assertFalse(checks['sqlite3']['passed'])
        self.assertEqual(checks['history_database']['state'], 'not_checked')
        self.assertFalse(checks['history_database']['repairable'])
        self.assertTrue(checks['storage']['passed'])

    def test_absent_optional_services_do_not_block_local_cad_or_expose_keys(self):
        secret = 'never-return-this-fixture-key'
        with patch.dict(os.environ, {'PPA_LLM_BASE_URL': '', 'PPA_LLM_MODEL': '', 'PPA_LLM_API_KEY': secret,
                                    'PPA_BAMBU_PATH': str(self.root / 'missing-studio')}), \
             patch('print_agent.slicer.probe_environment') as native:
            report = diagnose(self.root)
        self.assertTrue(report['ready'], report['checks'])
        self.assertFalse(report['provider']['configured'])
        self.assertFalse(report['slicer']['available'])
        native.assert_not_called()
        self.assertNotIn(secret, json.dumps(report))

    def test_corrupt_databases_are_distinguished_and_preserved_byte_for_byte(self):
        for filename, check_id, repairable in (
            ('history.sqlite3', 'history_database', True),
            ('profile-workspaces.sqlite3', 'workspace_database', False),
        ):
            with self.subTest(filename=filename), tempfile.TemporaryDirectory(dir=self.root) as temp:
                root = Path(temp)
                database = root / filename
                database.write_bytes(b'synthetic corrupted database; do not modify')
                before = {path.name: path.read_bytes() for path in root.iterdir()}
                report = diagnose(root)
                self.assertFalse(report['ready'])
                check = next(item for item in report['checks'] if item['id'] == check_id)
                self.assertFalse(check['passed'])
                self.assertEqual(check['state'], 'corrupt')
                self.assertEqual(check['repairable'], repairable)
                self.assertEqual({path.name: path.read_bytes() for path in root.iterdir()}, before)

    def test_empty_and_unrecognized_database_schemas_have_different_results(self):
        database = self.root / 'profile-workspaces.sqlite3'
        database.touch()
        uninitialized = diagnose(self.root)
        self.assertTrue(uninitialized['ready'], uninitialized['checks'])
        check = next(item for item in uninitialized['checks'] if item['id'] == 'workspace_database')
        self.assertEqual(check['state'], 'uninitialized')
        self.assertEqual(database.read_bytes(), b'')
        connection = sqlite3.connect(database)
        try:
            connection.execute('CREATE TABLE unrelated (value TEXT)')
            connection.commit()
        finally:
            connection.close()
        before = database.read_bytes()
        unsupported = diagnose(self.root)
        self.assertFalse(unsupported['ready'])
        check = next(item for item in unsupported['checks'] if item['id'] == 'workspace_database')
        self.assertEqual(check['state'], 'schema_unrecognized')
        self.assertFalse(check['repairable'])
        self.assertEqual(database.read_bytes(), before)

    def test_existing_application_databases_pass_read_only_checks(self):
        from print_agent.storage import JobStore
        from print_agent.workspaces import ProfileWorkspaceStore
        JobStore(self.root)
        ProfileWorkspaceStore(self.root)
        before = {path.name: path.read_bytes() for path in self.root.iterdir() if path.is_file()}
        report = diagnose(self.root)
        self.assertTrue(report['ready'], report['checks'])
        checks = {check['id']: check for check in report['checks']}
        self.assertEqual(checks['history_database']['state'], 'checked')
        self.assertEqual(checks['workspace_database']['state'], 'checked')
        self.assertEqual({path.name: path.read_bytes() for path in self.root.iterdir() if path.is_file()}, before)

    def test_incompatible_history_schema_does_not_promise_automatic_repair(self):
        database = self.root / 'history.sqlite3'
        connection = sqlite3.connect(database)
        try:
            connection.execute('CREATE TABLE jobs (id TEXT PRIMARY KEY)')
            connection.commit()
        finally:
            connection.close()
        before = database.read_bytes()
        report = diagnose(self.root)
        self.assertFalse(report['ready'])
        check = next(item for item in report['checks'] if item['id'] == 'history_database')
        self.assertEqual(check['state'], 'schema_unrecognized')
        self.assertFalse(check['repairable'])
        self.assertNotIn('앱을 다시 시작하면', check['detail'])
        self.assertEqual(database.read_bytes(), before)

    def test_busy_canonical_database_is_not_reported_as_corrupt(self):
        from print_agent.workspaces import ProfileWorkspaceStore
        ProfileWorkspaceStore(self.root)
        connection = sqlite3.connect(self.root / 'profile-workspaces.sqlite3')
        try:
            connection.execute('BEGIN EXCLUSIVE')
            report = diagnose(self.root)
        finally:
            connection.rollback()
            connection.close()
        self.assertFalse(report['ready'])
        check = next(item for item in report['checks'] if item['id'] == 'workspace_database')
        self.assertEqual(check['state'], 'not_checked')
        self.assertFalse(check['repairable'])
        self.assertTrue(diagnose(self.root)['ready'])


if __name__ == '__main__':
    unittest.main()
