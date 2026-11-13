from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from datetime import datetime
import math
from pathlib import Path
import tempfile
import threading
import unittest

from print_agent.workspaces import ProfileWorkspaceStore, WorkspaceConflict


def workspace_snapshot():
    """Synthetic input, deliberately including an unfinished edited document."""
    return {
        'schema_version': 1,
        'documents': [
            {
                'filename': 'original parent.json',
                'profile': {'name': 'Synthetic parent', 'nozzle_temperature': ['210']},
                'draft_text': '{"name":"Synthetic parent","nozzle_temperature":["215"]}',
            },
            {
                'filename': 'child.json',
                'profile': {'settings': {'name': 'Synthetic child', 'inherits': 'Synthetic parent'},
                            'validation': {'status': 'unverified'}},
                'draft_text': '  {\n  "settings": {"name": "unfinished 한글",\n',
            },
        ],
        'target_index': 1,
        'profile_text': '',
        'setup': {
            'printer_model': 'Synthetic printer',
            'printer_preset': 'Synthetic printer 0.4',
            'nozzle_diameter': '0.40',
            'plate_type': 'Textured PEI Plate',
            'extruder': 'Synthetic extruder',
            'feed_mode': 'Synthetic spool',
            'material_id': 'Synthetic material only',
            'material_identity_status': 'exact',
        },
    }


class WorkspaceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.store = ProfileWorkspaceStore(self.root)

    def tearDown(self):
        self.temp.cleanup()

    def test_restart_restores_originals_exact_unfinished_drafts_and_setup(self):
        snapshot = workspace_snapshot()
        original = deepcopy(snapshot)
        record = self.store.create('  내 필라멘트 작업  ', snapshot)
        self.assertEqual(record['title'], '내 필라멘트 작업')
        self.assertEqual(record['revision'], 1)
        self.assertRegex(record['id'], r'^[a-f0-9]{32}$')
        self.assertIsNotNone(datetime.fromisoformat(record['created_at']).utcoffset())
        self.assertEqual(record['created_at'], record['updated_at'])
        snapshot['documents'][0]['profile']['name'] = 'caller mutation'
        record['snapshot']['documents'][1]['draft_text'] = 'return-value mutation'
        reopened = ProfileWorkspaceStore(self.root).get(record['id'])
        self.assertEqual(reopened['snapshot'], original)
        self.assertNotIn('review', reopened)
        self.assertFalse((self.root / 'jobs').exists())

    def test_standalone_text_round_trips_without_parsing(self):
        snapshot = workspace_snapshot()
        snapshot.update(documents=[], target_index=0, profile_text='  {invalid\n\t한글')
        record = self.store.create('Pasted draft', snapshot)
        self.assertEqual(self.store.get(record['id'])['snapshot'], snapshot)
        self.assertEqual(self.store.list_workspaces()[0]['document_count'], 0)

    def test_list_returns_ordered_summaries_without_full_drafts(self):
        first = self.store.create('First', workspace_snapshot())
        second = self.store.create('Second', workspace_snapshot())
        changed = workspace_snapshot()
        changed['setup']['material_id'] = 'Edited material'
        updated = self.store.update(first['id'], 'Renamed', changed, first['revision'])
        self.assertEqual(updated['revision'], 2)
        self.assertEqual(updated['created_at'], first['created_at'])
        self.assertEqual(updated['snapshot'], changed)
        summaries = self.store.list_workspaces()
        self.assertEqual([item['id'] for item in summaries], [first['id'], second['id']])
        self.assertEqual(summaries[0]['title'], 'Renamed')
        self.assertEqual(summaries[0]['document_count'], 2)
        self.assertNotIn('snapshot', summaries[0])
        self.assertNotIn('draft_text', str(summaries))

    def test_stale_update_and_delete_preserve_newer_record_across_instances(self):
        first = self.store.create('Version one', workspace_snapshot())
        other = ProfileWorkspaceStore(self.root)
        changed = workspace_snapshot()
        changed['documents'][1]['draft_text'] = 'newer saved contents'
        current = other.update(first['id'], 'Version two', changed, 1)
        with self.assertRaises(WorkspaceConflict):
            self.store.update(first['id'], 'stale overwrite', workspace_snapshot(), 1)
        with self.assertRaises(WorkspaceConflict):
            self.store.delete(first['id'], 1)
        self.assertEqual(self.store.get(first['id']), current)
        self.assertEqual(self.store.delete(first['id'], 2), {'deleted': True, 'id': first['id']})
        with self.assertRaises(KeyError):
            other.get(first['id'])
        self.assertEqual(other.list_workspaces(), [])

    def test_simultaneous_updates_have_exactly_one_winner(self):
        record = self.store.create('Shared', workspace_snapshot())
        stores = [ProfileWorkspaceStore(self.root), ProfileWorkspaceStore(self.root)]
        barrier = threading.Barrier(2)

        def update(index):
            draft = workspace_snapshot()
            draft['documents'][1]['draft_text'] = f'writer {index}'
            barrier.wait(timeout=5)
            try:
                return stores[index].update(record['id'], f'writer {index}', draft, 1)
            except WorkspaceConflict:
                return None

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(update, range(2)))
        winners = [result for result in results if result is not None]
        self.assertEqual(len(winners), 1)
        self.assertEqual(winners[0]['revision'], 2)
        self.assertEqual(self.store.get(record['id']), winners[0])

    def test_invalid_update_leaves_existing_record_unchanged(self):
        record = self.store.create('Keep this', workspace_snapshot())
        invalid = workspace_snapshot()
        invalid['review'] = {'decision': 'ready_to_prepare'}
        with self.assertRaises(ValueError):
            self.store.update(record['id'], 'Should not replace', invalid, 1)
        self.assertEqual(self.store.get(record['id']), record)

    def test_unknown_ids_and_invalid_identifiers_do_not_touch_records(self):
        for invalid_id in ('../outside', '', 'A' * 32, 'a' * 31, 123, None):
            with self.subTest(invalid_id=invalid_id):
                with self.assertRaises(ValueError):
                    self.store.get(invalid_id)
        for action in (
            lambda: self.store.get('a' * 32),
            lambda: self.store.update('a' * 32, 'Unknown', workspace_snapshot(), 1),
            lambda: self.store.delete('a' * 32, 1),
        ):
            with self.assertRaises(KeyError):
                action()
        self.assertEqual(self.store.list_workspaces(), [])

    def test_title_and_revision_boundaries_do_not_accept_boolean_coercion(self):
        for title in ('', '   ', 'x' * 121, None, 123, '\ud800'):
            with self.subTest(title=repr(title)), self.assertRaises(ValueError):
                self.store.create(title, workspace_snapshot())
        record = self.store.create('x' * 120, workspace_snapshot())
        for revision in (True, False, 0, -1, 1.0, '1', None, 2**63):
            with self.subTest(revision=revision):
                with self.assertRaises(ValueError):
                    self.store.update(record['id'], 'title', workspace_snapshot(), revision)
                with self.assertRaises(ValueError):
                    self.store.delete(record['id'], revision)
        self.assertEqual(self.store.get(record['id']), record)

    def test_snapshot_shape_target_and_setup_are_strict(self):
        mutations = [
            lambda value: value.update(schema_version=True),
            lambda value: value.update(schema_version=2),
            lambda value: value.update(target_index=True),
            lambda value: value.update(target_index=-1),
            lambda value: value.update(target_index=2),
            lambda value: value.update(documents=[], target_index=1),
            lambda value: value.update(documents=value['documents'] * 33),
            lambda value: value.update(profile_text='duplicate selected draft'),
            lambda value: value.update(review={}),
            lambda value: value.pop('setup'),
            lambda value: value['setup'].pop('nozzle_diameter'),
            lambda value: value['setup'].update(secret='not a workspace field'),
            lambda value: value['setup'].update(nozzle_diameter=0.4),
            lambda value: value['setup'].update(printer_model='x' * 513),
            lambda value: value['setup'].update(material_identity_status='invented'),
            lambda value: value['documents'][0].update(filename=' '),
            lambda value: value['documents'][0].update(filename='x' * 241),
            lambda value: value['documents'][0].update(profile=[]),
            lambda value: value['documents'][0].update(draft_text={}),
            lambda value: value['documents'][0].update(open_path='/tmp/file'),
        ]
        for index, mutate in enumerate(mutations):
            snapshot = workspace_snapshot()
            mutate(snapshot)
            with self.subTest(case=index), self.assertRaises(ValueError):
                self.store.create('Invalid snapshot', snapshot)
        self.assertEqual(self.store.list_workspaces(), [])

    def test_json_values_must_round_trip_to_browser_without_coercion(self):
        values = [math.nan, math.inf, -math.inf, 2**53, -(2**53), 1e30, {1: 'key'},
                  ('not', 'JSON'), {'unpaired': '\ud800'}]
        for value in values:
            snapshot = workspace_snapshot()
            snapshot['documents'][0]['profile']['extra'] = value
            with self.subTest(value=repr(value)), self.assertRaises(ValueError):
                self.store.create('Invalid value', snapshot)
        valid = workspace_snapshot()
        valid['documents'][0]['profile']['extra'] = [None, False, 2**53-1, 0.123]
        self.assertEqual(self.store.create('Valid numeric forms', valid)['snapshot'], valid)

    def test_depth_and_cyclic_input_fail_before_serialization_recursion(self):
        nested = {}
        for _ in range(500):
            nested = {'nested': nested}
        cyclic = {}
        cyclic['self'] = cyclic
        for value in (nested, cyclic):
            snapshot = workspace_snapshot()
            snapshot['documents'][0]['profile'] = value
            with self.assertRaisesRegex(ValueError, '64'):
                self.store.create('Nested input', snapshot)

    def test_original_and_total_byte_budgets_are_separate(self):
        large_original = workspace_snapshot()
        large_original['documents'][0]['profile']['notes'] = 'x' * (2 * 1024 * 1024)
        with self.assertRaisesRegex(ValueError, '2 MiB'):
            self.store.create('Original too large', large_original)
        large_draft = workspace_snapshot()
        large_draft['documents'][1]['draft_text'] = '초' * (3 * 1024 * 1024)
        with self.assertRaisesRegex(ValueError, '8 MiB'):
            self.store.create('Draft too large', large_draft)
        retained = workspace_snapshot()
        retained['documents'][1]['draft_text'] = 'x' * (3 * 1024 * 1024)
        record = self.store.create('Draft larger than resolver input', retained)
        self.assertEqual(self.store.get(record['id'])['snapshot'], retained)


if __name__ == '__main__':
    unittest.main()
