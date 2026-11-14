"""A failed production startup must not initialize or alter either store."""
from contextlib import closing
from pathlib import Path
import sqlite3
import tempfile
import unittest

from fastapi.testclient import TestClient

from print_agent.app import create_app
from print_agent.backup import create_backup, restore_backup
from print_agent.runtime import StorageCompatibilityError, require_compatible_data
from print_agent.storage import JobStore
from print_agent.workspaces import ProfileWorkspaceStore


class StartupCompatibilityTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)

    def tearDown(self):
        self.temporary.cleanup()

    def assert_refused_without_data_changes(self):
        before = {str(p.relative_to(self.root)): p.read_bytes()
                  for p in self.root.rglob('*') if p.is_file() and p.name != '.printer-agent.lock'}
        with self.assertRaisesRegex(RuntimeError, '저장|호환|데이터'):
            with TestClient(create_app(self.root), base_url='http://127.0.0.1:8765'):
                self.fail('Incompatible stores must not start a ready application')
        after = {str(p.relative_to(self.root)): p.read_bytes()
                 for p in self.root.rglob('*') if p.is_file() and p.name != '.printer-agent.lock'}
        self.assertEqual(after, before)
        self.assertFalse((self.root / 'jobs').exists())

    def test_foreign_workspace_schema_refuses_before_creating_history(self):
        database = self.root / 'profile-workspaces.sqlite3'
        with closing(sqlite3.connect(database)) as connection, connection:
            connection.execute('CREATE TABLE foreign_workspace (id TEXT, value TEXT)')
            connection.execute('INSERT INTO foreign_workspace VALUES (?,?)', ('original', 'keep me'))
        self.assert_refused_without_data_changes()
        self.assertFalse((self.root / 'history.sqlite3').exists())

    def test_foreign_history_schema_refuses_before_creating_workspace(self):
        with closing(sqlite3.connect(self.root / 'history.sqlite3')) as connection, connection:
            connection.execute('CREATE TABLE foreign_jobs (id TEXT PRIMARY KEY)')
        self.assert_refused_without_data_changes()
        self.assertFalse((self.root / 'profile-workspaces.sqlite3').exists())

    def test_corrupt_canonical_workspace_is_not_treated_as_a_new_store(self):
        (self.root / 'profile-workspaces.sqlite3').write_bytes(b'synthetic damaged canonical database')
        self.assert_refused_without_data_changes()

    def test_database_with_only_an_unknown_view_is_not_empty(self):
        with closing(sqlite3.connect(self.root / 'profile-workspaces.sqlite3')) as connection, connection:
            connection.execute("CREATE VIEW foreign_workspace AS SELECT 'preserve' AS original")
        self.assert_refused_without_data_changes()

    def test_added_unknown_required_column_is_rejected_without_recovery_writes(self):
        store = ProfileWorkspaceStore(self.root)
        with closing(sqlite3.connect(store.db_path)) as connection, connection:
            connection.execute("ALTER TABLE profile_workspaces ADD COLUMN future_required TEXT NOT NULL DEFAULT 'future'")
        self.assert_refused_without_data_changes()

    def test_reordered_history_columns_are_refused_before_positional_writes(self):
        with closing(sqlite3.connect(self.root / 'history.sqlite3')) as connection, connection:
            connection.execute('''CREATE TABLE jobs (
                id TEXT PRIMARY KEY, title TEXT NOT NULL, created_at TEXT NOT NULL,
                template TEXT, status TEXT NOT NULL, user_outcome TEXT)''')
            connection.execute('INSERT INTO jobs VALUES (?,?,?,?,?,?)',
                               ('a' * 32, 'Original title', '2026-11-14', 'tray', 'interrupted', None))
        self.assert_refused_without_data_changes()

    def test_incompatible_column_type_and_constraints_are_refused(self):
        for identifier in ('id INTEGER PRIMARY KEY', 'id TEXT', 'id TEXT PRIMARY KEY DEFAULT 1'):
            with self.subTest(identifier=identifier):
                database = self.root / 'history.sqlite3'
                with closing(sqlite3.connect(database)) as connection, connection:
                    connection.execute(f'''CREATE TABLE jobs (
                        {identifier}, created_at TEXT NOT NULL, title TEXT NOT NULL,
                        template TEXT, status TEXT NOT NULL, user_outcome TEXT)''')
                self.assert_refused_without_data_changes()
                database.unlink()

    def test_closed_wal_database_probe_does_not_create_sidecars(self):
        store = ProfileWorkspaceStore(self.root)
        with closing(sqlite3.connect(store.db_path)) as connection:
            self.assertEqual(connection.execute('PRAGMA journal_mode=WAL').fetchone()[0], 'wal')
        before = {p.name: p.read_bytes() for p in self.root.iterdir()}
        self.assertEqual(require_compatible_data(self.root)['workspace_database']['state'], 'checked')
        self.assertEqual({p.name: p.read_bytes() for p in self.root.iterdir()}, before)

    def test_wal_backup_restores_exact_verified_inventory(self):
        store = ProfileWorkspaceStore(self.root)
        with closing(sqlite3.connect(store.db_path)) as connection:
            connection.execute('PRAGMA journal_mode=WAL')
        before = {p.name: p.read_bytes() for p in self.root.iterdir()}
        with tempfile.TemporaryDirectory() as outside:
            archive, destination = Path(outside) / 'workspace.zip', Path(outside) / 'restored'
            create_backup(self.root, archive)
            restore_backup(archive, destination)
            self.assertEqual({p.name: p.read_bytes() for p in destination.iterdir()}, before)

    def test_preflight_reads_committed_wal_schema_without_changing_originals(self):
        database = self.root / 'profile-workspaces.sqlite3'
        with closing(sqlite3.connect(database)) as connection:
            connection.execute('PRAGMA journal_mode=WAL')
            connection.execute('PRAGMA wal_autocheckpoint=0')
            connection.execute('CREATE TABLE foreign_workspace (id TEXT PRIMARY KEY, value TEXT)')
            connection.execute('INSERT INTO foreign_workspace VALUES (?,?)', ('original', 'committed WAL'))
            connection.commit()
            self.assertGreater((self.root / 'profile-workspaces.sqlite3-wal').stat().st_size, 0)
            before = {p.name: p.read_bytes() for p in self.root.iterdir()}
            with self.assertRaises(StorageCompatibilityError):
                require_compatible_data(self.root)
            self.assertEqual({p.name: p.read_bytes() for p in self.root.iterdir()}, before)

    def test_new_or_empty_databases_initialize_normally(self):
        for filename in ('history.sqlite3', 'profile-workspaces.sqlite3'):
            (self.root / filename).touch()
        with TestClient(create_app(self.root), base_url='http://127.0.0.1:8765') as client:
            self.assertEqual(client.get('/api/bootstrap').status_code, 200)
            self.assertEqual(client.get('/api/profile-workspaces').json(), {'workspaces': []})

    def test_corrupt_derived_history_still_recovers_from_canonical_jobs(self):
        store = JobStore(self.root)
        job_id, folder = store.reserve(request={'template': 'tray', 'width': 77})
        partial = folder / 'partial.stl'
        partial.write_bytes(b'preserved partial')
        damaged = b'synthetic damaged derived index'
        (self.root / 'history.sqlite3').write_bytes(damaged)
        with TestClient(create_app(self.root), base_url='http://127.0.0.1:8765') as client:
            job = client.get('/api/jobs/' + job_id).json()
            self.assertEqual(job['status'], 'interrupted')
            self.assertEqual(job['request']['width'], 77)
            self.assertEqual(job['artifacts'], {})
            self.assertEqual(client.get('/api/bootstrap').json()['storage']['recovery']['indexed'], 1)
        self.assertEqual(partial.read_bytes(), b'preserved partial')
        backups = list(self.root.glob('history-unreadable-*.sqlite3'))
        self.assertEqual(len(backups), 1)
        self.assertEqual(backups[0].read_bytes(), damaged)
