"""Named Studio inputs survive independently of jobs; lists never verify archives."""
from copy import deepcopy
import json
from pathlib import Path
import shutil
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from print_agent.runtime import StorageCompatibilityError, require_compatible_data
from print_agent.studio_revisions import StudioSettingsRevisionStore
from print_agent.studio_settings import derive_settings, settings_editor
from print_agent.studio_sources import StudioProjectStore
from print_agent.studio_workspaces import StudioWorkspaceStore, StudioWorkspaceIntegrityError
from print_agent.workspaces import WorkspaceConflict
from tests.studio_project_fixtures import project_bytes


class StudioWorkspaceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.sources = StudioProjectStore(self.root)
        self.source = self.sources.import_project('같은 이름.3mf', project_bytes())
        self.revisions = StudioSettingsRevisionStore(self.root, self.sources)
        original, _ = self.sources.read(self.source['source_id'])
        proposal = {'source_sha256': self.source['source']['sha256'],
                    'settings_sha256': self.source['settings_sha256'],
                    'values': {'nozzle_temperature': '225'}}
        _, review = derive_settings(original, proposal)
        self.edited = self.revisions.create(self.source['source_id'], proposal, review['review_sha256'])
        self.store = StudioWorkspaceStore(self.root, self.sources, self.revisions)
        self.drafts = {field['key']: field['value'] for field in settings_editor(original)['fields']}
        self.drafts.update(filament_flow_ratio=' 1. ', nozzle_temperature='x' * 33)

    def snapshot(self, edited=False):
        return {'schema_version': 1, 'source_id': self.source['source_id'],
                'settings_revision_id': self.edited['revision']['revision_id'] if edited else None,
                'source_sha256': self.source['source']['sha256'],
                'settings_sha256': self.source['settings_sha256'],
                'effective_settings_sha256': self.edited['revision']['effective_settings_sha256'] if edited else self.source['settings_sha256'],
                'draft_values': deepcopy(self.drafts)}

    def sql(self, statement, values=()):
        with sqlite3.connect(self.root / 'studio-workspaces.sqlite3') as db:
            db.execute(statement, values)

    def test_original_and_edited_zero_job_restart_preserves_exact_invalid_drafts(self):
        for edited in (False, True):
            with self.subTest(edited=edited):
                expected = self.snapshot(edited)
                record = self.store.create('  내 설정  ', expected)
                self.assertEqual(set(record), {'id', 'title', 'revision', 'created_at', 'updated_at', 'snapshot'})
                self.assertEqual(record['title'], '내 설정')
                self.assertEqual(record['revision'], 1)
                record['snapshot']['draft_values']['filament_flow_ratio'] = 'caller changed'
                reopened = StudioWorkspaceStore(self.root, self.sources, self.revisions).get(record['id'])
                self.assertEqual(set(reopened), {'workspace', 'source', 'settings_revision', 'editor'})
                self.assertEqual(reopened['workspace']['snapshot'], expected)
                self.assertEqual(reopened['source'], self.source)
                self.assertEqual(reopened['settings_revision'], self.edited if edited else None)
                self.assertEqual(reopened['editor']['source_id'], self.source['source_id'])
                self.assertEqual(reopened['editor']['settings_sha256'], self.source['settings_sha256'])
                self.assertEqual(next(field['value'] for field in reopened['editor']['fields'] if field['key'] == 'nozzle_temperature'), '200')
        self.assertFalse((self.root / 'jobs').exists())

    def test_saved_metadata_and_snapshot_are_sql_bounded_before_python_decode(self):
        record = self.store.create('Keep', self.snapshot())
        connect = self.store._connect
        def bounded_connection():
            db = connect()
            def text(raw):
                if len(raw) > 16384:
                    raise AssertionError('SQLite transferred an oversized stored value')
                return raw.decode('utf-8')
            db.text_factory = text
            return db
        for column, raw in [('title', 'x'*20000), ('created_at', 'x'*20000),
                            ('updated_at', 'x'*20000), ('snapshot_json', ' '*20000)]:
            self.sql(f'UPDATE studio_workspaces SET {column}=? WHERE id=?', (raw, record['id']))
            with patch.object(self.store, '_connect', side_effect=bounded_connection):
                with self.subTest(column=column), self.assertRaises(StudioWorkspaceIntegrityError):
                    self.store.get(record['id'])
                self.assertEqual(self.store.list_entries('workspaces')['items'][0]['metadata_status'], 'unreadable')
            self.sql(f'UPDATE studio_workspaces SET {column}=? WHERE id=?',
                     (json.dumps(record['snapshot']) if column == 'snapshot_json' else record[column], record['id']))

    def test_cross_instance_stale_writes_and_delete_preserve_immutable_inputs(self):
        first = self.store.create('First', self.snapshot(True))
        other = StudioWorkspaceStore(self.root, self.sources, self.revisions)
        current = other.update(first['id'], 'Second', self.snapshot(), 1)
        self.assertEqual(current['revision'], 2)
        self.assertEqual(current['created_at'], first['created_at'])
        with self.assertRaises(WorkspaceConflict):
            self.store.update(first['id'], 'stale', self.snapshot(), 1)
        with self.assertRaises(WorkspaceConflict):
            self.store.delete(first['id'], 1)
        self.assertEqual(self.store.get(first['id'])['workspace'], current)
        self.assertIsNone(other.delete(first['id'], 2))
        with self.assertRaises(KeyError):
            self.store.get(first['id'])
        self.assertEqual(self.sources.get(self.source['source_id']), self.source)
        self.assertEqual(self.revisions.get(self.edited['revision']['revision_id']), self.edited)

    def test_maximum_revision_update_rolls_back(self):
        record = self.store.create('Keep', self.snapshot())
        self.sql('UPDATE studio_workspaces SET revision=? WHERE id=?', (2**53-2, record['id']))
        before = self.store.get(record['id'])['workspace']
        with self.assertRaises(ValueError):
            self.store.update(record['id'], 'Overflow', self.snapshot(), 2**53-2)
        self.assertEqual(self.store.get(record['id'])['workspace'], before)

    def test_new_input_shape_bounds_hashes_and_revision_are_strict(self):
        mutations = [lambda v: v.update(schema_version=True), lambda v: v.update(extra={}),
                     lambda v: v.update(source_id='A'*32), lambda v: v.update(settings_revision_id='bad'),
                     lambda v: v.update(source_sha256='0'*64), lambda v: v.update(settings_sha256='0'*64),
                     lambda v: v.update(effective_settings_sha256='0'*64),
                     lambda v: v.update(draft_values=[]), lambda v: v['draft_values'].pop('bed_temperature'),
                     lambda v: v['draft_values'].update(nozzle_temperature=225),
                     lambda v: v['draft_values'].update(nozzle_temperature='x'*513),
                     lambda v: v['draft_values'].update(nozzle_temperature='\ud800')]
        for mutate in mutations:
            value = self.snapshot()
            mutate(value)
            with self.subTest(snapshot=repr(value)), self.assertRaises(ValueError):
                self.store.create('Invalid', value)
        for title in ('', ' ', 'x'*121, None, '\ud800'):
            with self.subTest(title=repr(title)), self.assertRaises(ValueError):
                self.store.create(title, self.snapshot())
        record = self.store.create('x'*120, {**self.snapshot(), 'draft_values': None})
        for revision in (True, 0, -1, 1.0, '1', 2**53-1):
            with self.subTest(revision=revision):
                with self.assertRaises(ValueError):
                    self.store.update(record['id'], 'bad', self.snapshot(), revision)
                with self.assertRaises(ValueError):
                    self.store.delete(record['id'], revision)
        value = self.snapshot()
        value['draft_values'] = {key: '😀'*512 for key in self.drafts}
        self.assertEqual(self.store.create('bounded unicode', value)['snapshot'], value)
        self.assertEqual(self.store.get(record['id'])['workspace'], record)

    def test_update_and_create_verify_named_source_revision_and_leave_rows_unchanged(self):
        record = self.store.create('Keep', self.snapshot(True))
        other = self.sources.import_project('Different identity.3mf', project_bytes())
        invalid = self.snapshot(True)
        invalid['source_id'] = other['source_id']
        for action in (lambda: self.store.create('Mismatch', invalid),
                       lambda: self.store.update(record['id'], 'Mismatch', invalid, 1)):
            with self.assertRaises(ValueError):
                action()
        self.assertEqual(self.store.get(record['id'])['workspace'], record)
        path = self.root / 'studio-projects' / self.source['source_id'] / 'receipt.json'
        raw = path.read_bytes()
        path.unlink()
        with self.assertRaises(StudioWorkspaceIntegrityError):
            self.store.get(record['id'])
        path.write_bytes(raw)
        self.assertEqual(self.store.get(record['id'])['workspace'], record)

    def test_escaped_draft_snapshot_budget_is_independent_of_character_budget(self):
        snapshot = self.snapshot()
        snapshot['draft_values'] = {key: '\x00'*512 for key in self.drafts}
        with self.assertRaises(ValueError):
            self.store.create('Too many encoded bytes', snapshot)
        self.assertEqual(self.store.list_entries('workspaces')['items'], [])

    def test_catalog_lookahead_opens_no_off_page_receipt_or_workspace_payload(self):
        from print_agent import studio_workspaces
        last = 'f'*32
        source_folder = self.root / 'studio-projects' / last
        source_folder.mkdir()
        receipt = source_folder / 'receipt.json'
        receipt.write_text((self.root / 'studio-projects' / self.source['source_id'] / 'receipt.json').read_text().replace(self.source['source_id'], last))
        read_regular = studio_workspaces._read_regular
        def selected_only(path, maximum):
            if path != receipt:
                raise AssertionError('Off-page metadata was opened')
            return read_regular(path, maximum)
        with patch.object(studio_workspaces, '_read_regular', side_effect=selected_only):
            page = self.store.list_entries('sources', limit=1)
        self.assertEqual(page['items'][0]['id'], last)
        self.assertEqual(page['items'][0]['metadata_status'], 'recorded')
        self.assertEqual(page['next_cursor'], last)
        first = self.store.create('First', self.snapshot())
        second = self.store.create('Second', self.snapshot())
        selected = max(first['id'], second['id'])
        read = self.store._read
        def selected_row(db, identifier):
            if identifier != selected:
                raise AssertionError('Off-page workspace payload was opened')
            return read(db, identifier)
        with patch.object(self.store, '_read', side_effect=selected_row):
            page = self.store.list_entries('workspaces', limit=1)
        self.assertEqual(page['items'][0]['id'], selected)
        self.assertEqual(page['next_cursor'], selected)

    def test_missing_named_record_remains_key_error_but_missing_reference_is_integrity_error(self):
        with self.assertRaises(KeyError):
            self.store.get('a'*32)
        for edited in (False, True):
            record = self.store.create('Keep', self.snapshot(edited))
            path = (self.root / 'studio-settings-revisions' / self.edited['revision']['revision_id'] / 'revision.json') if edited else (self.root / 'studio-projects' / self.source['source_id'] / 'receipt.json')
            saved = path.read_bytes()
            path.unlink()
            with self.assertRaises(StudioWorkspaceIntegrityError):
                self.store.get(record['id'])
            path.write_bytes(saved)

    def test_reference_identity_mismatch_and_tampered_archives_fail_on_open(self):
        record = self.store.create('Keep', self.snapshot(True))
        for key, value in [('source_sha256', '0'*64), ('settings_sha256', '0'*64),
                           ('effective_settings_sha256', '0'*64), ('source_id', 'f'*32),
                           ('settings_revision_id', 'f'*32)]:
            snapshot = self.snapshot(True)
            snapshot[key] = value
            self.sql('UPDATE studio_workspaces SET snapshot_json=? WHERE id=?', (json.dumps(snapshot), record['id']))
            with self.subTest(key=key), self.assertRaises(StudioWorkspaceIntegrityError):
                self.store.get(record['id'])
        self.sql('UPDATE studio_workspaces SET snapshot_json=? WHERE id=?', (json.dumps(self.snapshot(True)), record['id']))
        archive = self.root / 'studio-projects' / self.source['source_id'] / 'source.3mf'
        archive.write_bytes(b'changed')
        with self.assertRaises(StudioWorkspaceIntegrityError):
            self.store.get(record['id'])

    def test_saved_rows_reject_bounded_malformed_duplicate_and_nonfinite_json(self):
        record = self.store.create('Keep', self.snapshot())
        valid = json.dumps(self.snapshot())
        for raw in (' '*16385, '{', '{"schema_version":1,'+valid[1:], valid.replace('"schema_version": 1', '"schema_version": NaN'), '[]'):
            self.sql('UPDATE studio_workspaces SET snapshot_json=? WHERE id=?', (raw, record['id']))
            with self.subTest(raw=raw[:80]), self.assertRaises(StudioWorkspaceIntegrityError):
                self.store.get(record['id'])
            item = self.store.list_entries('workspaces')['items'][0]
            self.assertEqual(item['metadata_status'], 'unreadable')
            self.assertNotIn('draft_values', str(item))

    def test_saved_invalid_utf8_is_reported_as_row_integrity(self):
        record = self.store.create('Keep', self.snapshot())
        self.sql("UPDATE studio_workspaces SET title=CAST(X'80' AS TEXT) WHERE id=?", (record['id'],))
        with self.assertRaises(StudioWorkspaceIntegrityError):
            self.store.get(record['id'])
        self.assertEqual(self.store.list_entries('workspaces')['items'][0]['metadata_status'], 'unreadable')

    def test_saved_row_metadata_is_validated_before_exposure(self):
        record = self.store.create('Keep', self.snapshot())
        for column, bad in [('title', ' '), ('title','x'*121), ('revision', 2**53-1),
                            ('created_at','not a timestamp'), ('updated_at','2026-11-15T00:00:00')]:
            self.sql(f'UPDATE studio_workspaces SET {column}=? WHERE id=?', (bad, record['id']))
            with self.subTest(column=column, bad=bad), self.assertRaises(StudioWorkspaceIntegrityError):
                self.store.get(record['id'])
            self.sql(f'UPDATE studio_workspaces SET {column}=? WHERE id=?', (record[column], record['id']))

    def test_supported_and_unsupported_retained_imports_remain_recorded_metadata(self):
        for filename, overrides, expected_text in (
                ('numeric.3mf', {'nozzle_diameter': [0.4]}, '0.4'),
                ('multi.3mf', {'filament_type': ['PLA', 'PETG'], 'filament_settings_id': ['First', 'Second']}, '["First","Second"]')):
            source = self.sources.import_project(filename, project_bytes(settings_overrides=overrides))
            self.assertFalse(source['supported'])
            with patch.object(self.sources, 'read', side_effect=AssertionError('Catalog opened an archive')):
                item = next(item for item in self.store.list_entries('sources')['items'] if item['id'] == source['source_id'])
            self.assertEqual(item['metadata_status'], 'recorded')
            self.assertIn(expected_text, item['summary'])
            self.assertIn('지원 범위', item['detail'])
            snapshot = {**self.snapshot(), 'source_id': source['source_id'],
                        'source_sha256': source['source']['sha256'], 'settings_sha256': source['settings_sha256'],
                        'effective_settings_sha256': source['settings_sha256']}
            with self.assertRaises(ValueError):
                self.store.create('Unsupported setup', snapshot)

    def test_catalog_pagination_equal_filenames_legacy_metadata_and_no_archive_reads(self):
        second = self.sources.import_project('같은 이름.3mf', project_bytes())
        records = [self.store.create('Name '+str(i), self.snapshot(i == 1)) for i in range(3)]
        with patch.object(self.sources, 'read', side_effect=AssertionError('archive reads forbidden')), \
             patch.object(self.revisions, 'read', side_effect=AssertionError('archive reads forbidden')):
            for kind, ids in [('workspaces', [r['id'] for r in records]),
                              ('sources', [self.source['source_id'], second['source_id']]),
                              ('revisions', [self.edited['revision']['revision_id']])]:
                seen = []
                before = None
                while True:
                    page = self.store.list_entries(kind, limit=1, before=before)
                    self.assertEqual(set(page), {'items', 'next_cursor'})
                    seen += [item['id'] for item in page['items']]
                    for item in page['items']:
                        self.assertEqual(set(item), {'id','kind','title','created_at','updated_at','source_id','settings_revision_id','revision','has_draft','metadata_status','detail','summary'})
                        self.assertEqual(item['metadata_status'], 'recorded')
                        self.assertLessEqual(len(item['summary']), 1200)
                        self.assertNotIn('x'*33, str(item))
                    before = page['next_cursor']
                    if before is None:
                        break
                self.assertEqual(seen, sorted(ids, reverse=True))
            source_items = self.store.list_entries('sources')['items']
            self.assertEqual(len({item['id'] for item in source_items}), 2)
            self.assertTrue(all('같은 이름' in item['title'] for item in source_items))
            self.assertIn('nozzle_temperature', self.store.list_entries('revisions')['items'][0]['summary'])
        self.assertFalse((self.root / 'jobs').exists())

    def test_catalog_opens_only_selected_page_and_one_bad_item_does_not_hide_healthy(self):
        bad_id = 'f'*32
        folder = self.root / 'studio-projects' / bad_id
        folder.mkdir()
        (folder / 'receipt.json').write_bytes(b'{')
        page = self.store.list_entries('sources', limit=1)
        self.assertEqual(page['items'][0]['id'], bad_id)
        self.assertEqual(page['items'][0]['metadata_status'], 'unreadable')
        self.assertEqual(page['next_cursor'], bad_id)
        page = self.store.list_entries('sources', before=bad_id)
        self.assertEqual(page['items'][0]['id'], self.source['source_id'])
        self.assertEqual(page['items'][0]['metadata_status'], 'recorded')
        for bad in (b' '*262145, b'{"schema_version":NaN}', b'{"x":1,"x":2}'):
            (folder / 'receipt.json').write_bytes(bad)
            self.assertEqual(self.store.list_entries('sources', limit=1)['items'][0]['metadata_status'], 'unreadable')

    def test_unpaired_surrogate_metadata_isolated_from_healthy_neighbor_and_serialization(self):
        broken = self.sources.import_project('Broken.3mf', project_bytes())
        path = self.root / 'studio-projects' / broken['source_id'] / 'receipt.json'
        valid = json.loads(path.read_text())
        for field in ('filename', 'summary'):
            value = deepcopy(valid)
            if field == 'filename':
                value['inspection']['source']['filename'] = 'bad' + chr(0xd800)
            else:
                value['inspection']['summary']['filament_name'] = ['bad' + chr(0xd800), 'Second']
            path.write_text(json.dumps(value), encoding='utf-8')
            page = self.store.list_entries('sources')
            by_id = {item['id']: item for item in page['items']}
            with self.subTest(field=field):
                self.assertEqual(by_id[broken['source_id']]['metadata_status'], 'unreadable')
                self.assertEqual(by_id[self.source['source_id']]['metadata_status'], 'recorded')
                json.dumps(page, ensure_ascii=False).encode('utf-8')

    def test_invalid_catalog_queries_fail_before_reading(self):
        for kind, kwargs in [('bad', {}), ('sources', {'limit':True}), ('sources', {'limit':0}),
                             ('sources', {'limit':101}), ('sources', {'before':'../escape'})]:
            with self.subTest(kind=kind, kwargs=kwargs), self.assertRaises(ValueError):
                self.store.list_entries(kind, **kwargs)

    def test_incompatible_database_is_rejected_without_mutation(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            database = root / 'studio-workspaces.sqlite3'
            for content in (b'not a sqlite database', b''):
                database.write_bytes(content)
                before = database.read_bytes()
                with self.assertRaises(StorageCompatibilityError):
                    StudioWorkspaceStore(root, StudioProjectStore(root), StudioSettingsRevisionStore(root, StudioProjectStore(root)))
                self.assertEqual(database.read_bytes(), before)
            database.unlink()
            with sqlite3.connect(database) as db:
                db.execute('CREATE TABLE studio_workspaces (id TEXT PRIMARY KEY)')
            before = database.read_bytes()
            with self.assertRaises(StorageCompatibilityError):
                require_compatible_data(root)
            self.assertEqual(database.read_bytes(), before)


if __name__ == '__main__':
    unittest.main()
