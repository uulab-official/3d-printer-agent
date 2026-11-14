"""Recovery and paging use synthetic job files, never native printer actions."""
import base64
import copy
import json
import sqlite3
import tempfile
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch

from print_agent import storage
from print_agent.schemas import GeometryRequest


def result_fixture(folder, request=None):
    request = GeometryRequest.model_validate(request or {}).model_dump(mode='json')
    (folder / 'model.stl').write_bytes(b'synthetic storage fixture, not an STL model')
    return {'template': request['template'], 'parameters': request,
            'dimensions_mm': dict(zip('xyz', (request['width'], request['depth'], request['height']))),
            'geometry_status': 'validated', 'print_status': 'not_tested',
            'files': {'stl': 'model.stl'}, 'mesh': {'vertices': [], 'faces': []},
            'checks': [], 'warnings': [], 'volume_mm3': 100}


class RecoveryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.store = storage.JobStore(self.root)

    def tearDown(self):
        self.temp.cleanup()

    def finish_job(self):
        job_id, folder = self.store.reserve()
        return self.store.finish(job_id, result_fixture(folder)), folder

    def test_explicit_recovery_interrupts_once_and_preserves_input_and_partial_bytes(self):
        request = GeometryRequest(width=143).model_dump(mode='json')
        source = {'kind': 'project_catalog', 'recipe': {'title': 'Synthetic source'}, 'customized': True}
        expected_request, expected_source = copy.deepcopy(request), copy.deepcopy(source)
        job_id, folder = self.store.reserve(request=request, design_source=source)
        request['width'] = 399
        source['recipe']['title'] = 'Mutated caller object'
        (folder / 'model.stl').write_bytes(b'partial original output')
        reopened = storage.JobStore(self.root)
        self.assertEqual(reopened.get(job_id)['status'], 'generating')
        self.assertEqual(reopened.recover(), {'indexed': 1, 'interrupted': 1, 'unreadable': 0})
        job = reopened.get(job_id)
        self.assertEqual(job['status'], 'interrupted')
        self.assertEqual(job['request'], expected_request)
        self.assertEqual(job['design_source'], expected_source)
        self.assertIsNone(job['result'])
        self.assertEqual(job['artifacts'], {})
        self.assertIsNone(job['bundle_url'])
        self.assertEqual((folder / 'model.stl').read_bytes(), b'partial original output')
        with self.assertRaises(KeyError):
            reopened.bundle(job_id)
        before = (folder / 'job.json').read_bytes()
        self.assertEqual(reopened.recover(), {'indexed': 1, 'interrupted': 0, 'unreadable': 0})
        self.assertEqual((folder / 'job.json').read_bytes(), before)
        self.assertEqual([e['type'] for e in job['events']], ['generation_interrupted'])

    def test_reserved_source_is_reused_and_cannot_be_replaced_at_finish(self):
        source = {'kind': 'project_catalog', 'recipe': {'title': 'Original synthetic source'}}
        request = GeometryRequest(width=145).model_dump(mode='json')
        job_id, folder = self.store.reserve(request=request, design_source=source)
        result = result_fixture(folder, request)
        with self.assertRaises(ValueError):
            self.store.finish(job_id, result, design_source={'kind': 'different'})
        self.assertEqual(self.store.get(job_id)['design_source'], source)
        job = self.store.finish(job_id, result)
        self.assertEqual(job['design_source'], source)
        self.assertEqual(job['request'], request)
        self.assertEqual(json.loads((folder / 'manifest.json').read_text())['design_source'], source)

    def test_untyped_or_changed_request_cannot_be_saved_as_completed(self):
        with self.assertRaises(ValueError):
            self.store.reserve(request={'template': 'tray', 'code': 'unsupported'})
        self.assertEqual(self.store.list_jobs(), [])
        job_id, folder = self.store.reserve(request={'template': 'tray', 'width': 140})
        with self.assertRaises(ValueError):
            self.store.finish(job_id, result_fixture(folder, {'width': 141}))
        self.assertEqual(self.store.get(job_id)['status'], 'generating')

    def test_missing_index_is_rebuilt_from_completed_and_failed_jobs(self):
        completed, _ = self.finish_job()
        failed_id, _ = self.store.reserve()
        self.store.fail(failed_id, 'synthetic generation failure')
        self.store.db_path.unlink()
        reopened = storage.JobStore(self.root)
        self.assertEqual(reopened.list_jobs(), [])
        self.assertEqual(reopened.recover(), {'indexed': 2, 'interrupted': 0, 'unreadable': 0})
        rows = {row['id']: row for row in reopened.list_jobs()}
        self.assertEqual(rows[completed['id']]['status'], 'geometry_validated')
        self.assertEqual(rows[failed_id]['status'], 'failed')

    def test_failed_index_commit_is_reconciled_from_atomic_job_record(self):
        job, _ = self.finish_job()
        with patch('print_agent.storage.sqlite3.connect', side_effect=sqlite3.OperationalError('synthetic index failure')):
            with self.assertRaises(sqlite3.OperationalError):
                self.store.record_outcome(job['id'], 'success', 'saved before index failure')
        reopened = storage.JobStore(self.root)
        self.assertIsNone(reopened.list_jobs()[0]['user_outcome'])
        self.assertEqual(reopened.get(job['id'])['user_outcome']['result'], 'success')
        self.assertEqual(reopened.recover()['indexed'], 1)
        self.assertEqual(reopened.list_jobs()[0]['user_outcome'], reopened.get(job['id'])['user_outcome'])

    def test_corrupt_index_requires_explicit_recovery_and_keeps_exact_backup(self):
        job, folder = self.finish_job()
        record = (folder / 'job.json').read_bytes()
        damaged = b'synthetic damaged SQLite index\x00\xff'
        self.store.db_path.write_bytes(damaged)
        reopened = storage.JobStore(self.root)
        with self.assertRaises(storage.JobRecordError):
            reopened.get(job['id'])
        before = set((self.root / 'jobs').iterdir())
        with self.assertRaises(storage.JobRecordError):
            reopened.reserve()
        self.assertEqual(set((self.root / 'jobs').iterdir()), before)
        self.assertEqual(self.store.db_path.read_bytes(), damaged)
        self.assertEqual(reopened.recover(), {'indexed': 1, 'interrupted': 0, 'unreadable': 0})
        backups = list(self.root.glob('history-unreadable-*.sqlite3'))
        self.assertEqual(len(backups), 1)
        self.assertEqual(backups[0].read_bytes(), damaged)
        self.assertEqual((folder / 'job.json').read_bytes(), record)
        self.assertEqual(reopened.get(job['id'])['status'], 'geometry_validated')
        reopened.recover()
        self.assertEqual(list(self.root.glob('history-unreadable-*.sqlite3')), backups)

    def test_failed_corrupt_index_preservation_never_replaces_original(self):
        job, folder = self.finish_job()
        record = (folder / 'job.json').read_bytes()
        damaged = b'damaged index to preserve'
        self.store.db_path.write_bytes(damaged)
        reopened = storage.JobStore(self.root)
        original_open = Path.open
        def fail_backup(path, *args, **kwargs):
            if path.name.startswith('history-unreadable-'):
                raise PermissionError('synthetic backup failure')
            return original_open(path, *args, **kwargs)
        with patch.object(Path, 'open', fail_backup), self.assertRaises(storage.JobRecordError):
            reopened.recover()
        self.assertEqual(self.store.db_path.read_bytes(), damaged)
        self.assertEqual((folder / 'job.json').read_bytes(), record)
        with self.assertRaises(storage.JobRecordError):
            reopened.list_jobs()

    def test_oversized_update_preserves_last_readable_record(self):
        job, folder = self.finish_job()
        before = (folder / 'job.json').read_bytes()
        with patch('print_agent.storage._MAX_RECORD_BYTES', len(before) + 10), self.assertRaises(ValueError):
            self.store.record_outcome(job['id'], 'success', 'long synthetic notes' * 30)
        self.assertEqual((folder / 'job.json').read_bytes(), before)
        self.assertIsNone(self.store.get(job['id'])['user_outcome'])

    def test_damaged_records_including_unindexed_folders_remain_visible_and_untouched(self):
        good, _ = self.finish_job()
        corrupted = {}
        for content in (b'{broken JSON', b'[]', b'{"id":"wrong"}'):
            job_id, folder = self.store.reserve()
            (folder / 'job.json').write_bytes(content)
            corrupted[job_id] = (folder, content)
        orphan = uuid.uuid4().hex
        orphan_dir = self.root / 'jobs' / orphan
        orphan_dir.mkdir()
        (orphan_dir / 'job.json').write_bytes(b'unindexed damaged record')
        corrupted[orphan] = (orphan_dir, b'unindexed damaged record')
        self.assertEqual(self.store.recover(), {'indexed': 1, 'interrupted': 0, 'unreadable': 4})
        rows = {row['id']: row for row in self.store.list_jobs()}
        self.assertEqual(rows[good['id']]['status'], 'geometry_validated')
        self.assertEqual(set(rows), {good['id'], *corrupted})
        for job_id, (folder, original) in corrupted.items():
            self.assertEqual(rows[job_id]['status'], 'unreadable')
            self.assertTrue(rows[job_id]['diagnostic'])
            self.assertEqual((folder / 'job.json').read_bytes(), original)
            with self.assertRaises(storage.JobRecordError):
                self.store.get(job_id)
        before = self.store.list_jobs()
        self.assertEqual(self.store.recover()['unreadable'], 4)
        self.assertEqual(self.store.list_jobs(), before)

    def test_missing_indexed_job_file_does_not_disappear(self):
        job, folder = self.finish_job()
        (folder / 'job.json').unlink()
        self.assertEqual(self.store.recover(), {'indexed': 0, 'interrupted': 0, 'unreadable': 1})
        self.assertEqual(self.store.list_jobs()[0]['id'], job['id'])
        self.assertEqual(self.store.list_jobs()[0]['status'], 'unreadable')
        self.assertTrue((folder / 'model.stl').is_file())

    def test_bad_identity_is_unreadable_without_reading_another_job(self):
        first, folder = self.finish_job()
        second, _ = self.finish_job()
        data = json.loads((folder / 'job.json').read_text())
        data['id'] = second['id']
        (folder / 'job.json').write_text(json.dumps(data))
        with self.assertRaises(storage.JobRecordError):
            self.store.get(first['id'])
        self.assertEqual(self.store.get(second['id'])['id'], second['id'])

    def test_malformed_nested_slice_is_an_unreadable_record(self):
        job, folder = self.finish_job()
        path = folder / 'job.json'
        damaged = json.loads(path.read_text())
        damaged['latest_slice'] = {'recorded_at': '2026-11-14T00:00:00+00:00', 'plan': {}, 'execution': []}
        content = json.dumps(damaged).encode()
        path.write_bytes(content)
        with self.assertRaises(storage.JobRecordError):
            self.store.get(job['id'])
        self.assertEqual(self.store.recover()['unreadable'], 1)
        self.assertEqual(path.read_bytes(), content)

    def test_abandoned_slice_is_interrupted_without_invalidating_completed_cad(self):
        job, folder = self.finish_job()
        old_slice = folder / 'old.gcode.3mf'
        old_slice.write_bytes(b'synthetic old slice')
        self.store.record_slice(job['id'], {'ready': True}, {'status': 'sliced', 'output_path': str(old_slice)})
        current = self.store.begin_slice(job['id'])
        self.assertEqual(current['latest_slice']['phase'], 'running')
        self.assertNotIn('sliced_three_mf', current['artifacts'])
        with self.assertRaises(KeyError):
            self.store.artifact_path(job['id'], 'sliced_three_mf')
        reopened = storage.JobStore(self.root)
        self.assertEqual(reopened.recover(), {'indexed': 1, 'interrupted': 0, 'unreadable': 0})
        current = reopened.get(job['id'])
        self.assertEqual(current['status'], 'geometry_validated')
        self.assertEqual(current['latest_slice']['phase'], 'interrupted')
        self.assertEqual(current['latest_slice']['execution']['status'], 'interrupted')
        self.assertNotIn('sliced_three_mf', current['artifacts'])
        self.assertTrue(old_slice.is_file())
        self.assertEqual(reopened.read_artifact(job['id'], 'stl')[1], (folder / 'model.stl').read_bytes())
        reopened.recover()
        self.assertEqual([event['type'] for event in reopened.get(job['id'])['events']].count('slicer_interrupted'), 1)

    def test_finished_slice_closes_running_phase(self):
        job, _ = self.finish_job()
        self.store.begin_slice(job['id'])
        current = self.store.record_slice(job['id'], {'ready': False}, None)
        self.assertEqual(current['latest_slice']['phase'], 'finished')
        self.assertEqual(current['status'], 'geometry_validated')


class PagingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.store = storage.JobStore(Path(self.temp.name))

    def tearDown(self):
        self.temp.cleanup()

    def test_cursor_visits_all_old_jobs_once_across_ties_and_new_arrivals(self):
        with patch('print_agent.storage.now_iso', return_value='2026-11-14T00:00:00+00:00'):
            ids = [self.store.reserve()[0] for _ in range(125)]
        page = self.store.list_jobs_page(limit=20)
        found = [row['id'] for row in page['jobs']]
        new_id = self.store.reserve()[0]
        while page['next_cursor'] is not None:
            page = self.store.list_jobs_page(limit=20, before=page['next_cursor'])
            found.extend(row['id'] for row in page['jobs'])
        self.assertEqual(found, sorted(ids, reverse=True))
        self.assertNotIn(new_id, found)
        self.assertEqual(len(self.store.list_jobs()), 100)
        self.assertEqual(self.store.list_jobs_page(limit=1)['jobs'][0]['id'], new_id)

    def test_empty_and_exact_final_pages_have_no_cursor(self):
        self.assertEqual(self.store.list_jobs_page(), {'jobs': [], 'next_cursor': None})
        self.store.reserve()
        self.assertIsNone(self.store.list_jobs_page(limit=1)['next_cursor'])

    def test_invalid_limits_and_cursors_fail_with_readable_validation(self):
        for limit in (0, 101, True, 1.5, '20'):
            with self.subTest(limit=limit), self.assertRaises(ValueError):
                self.store.list_jobs_page(limit=limit)
        encoded = lambda value: base64.urlsafe_b64encode(json.dumps(value).encode()).decode().rstrip('=')
        cursors = ['', 'not valid!', 'a' * 513, encoded({}),
                   encoded([True, '2026-11-14T00:00:00+00:00', 'a' * 32]),
                   encoded([1, 'bad date', 'a' * 32]),
                   encoded([1, '2026-11-14T00:00:00+00:00', '../outside'])]
        for cursor in cursors:
            with self.subTest(cursor=cursor[:60]), self.assertRaises(ValueError):
                self.store.list_jobs_page(before=cursor)
