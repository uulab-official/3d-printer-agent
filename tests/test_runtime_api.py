"""HTTP behavior at local recovery, admission and verified-download boundaries."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from print_agent.app import CAD_LOCK, SLICER_LOCK, create_app
from print_agent.schemas import GeometryRequest
from print_agent.storage import JobStore


class RuntimeApiTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.app = create_app(self.root, test_mode=True)
        self.client = TestClient(self.app, raise_server_exceptions=False)
        self.headers = {'X-Session-Token': self.client.get('/api/bootstrap').json()['session_token']}

    def tearDown(self):
        self.client.close()
        self.temp.cleanup()

    def saved_job(self):
        job_id, folder = self.app.state.store.reserve()
        (folder / 'model.3mf').write_bytes(b'synthetic receipt fixture')
        result = {'template': 'tray', 'parameters': GeometryRequest(template='tray').model_dump(),
                  'dimensions_mm': {'x': 120, 'y': 80, 'z': 35}, 'volume_mm3': 100,
                  'geometry_status': 'validated', 'print_status': 'not_tested',
                  'checks': [], 'warnings': [], 'mesh': {'vertices': [], 'faces': []},
                  'files': {'three_mf': 'model.3mf'}}
        return self.app.state.store.finish(job_id, result), folder

    def test_expired_and_non_ascii_session_tokens_return_recoverable_403(self):
        for token in (b'old-session', b'\xff'):
            with self.subTest(token=token):
                response = self.client.post('/api/models', json={'template': 'tray'},
                                            headers={b'X-Session-Token': token})
                self.assertEqual(response.status_code, 403)
                self.assertEqual(response.json()['code'], 'session_expired')
        self.assertEqual(self.app.state.store.list_jobs(), [])

    def test_bootstrap_reports_the_actual_storage_location(self):
        storage = self.client.get('/api/bootstrap').json()['storage']
        self.assertEqual(storage['path'], str(self.root.resolve()))
        self.assertEqual(storage['source'], 'argument')
        self.assertFalse(storage['legacy'])
        self.assertEqual(storage['recovery'], {'indexed': 0, 'interrupted': 0, 'unreadable': 0})
        self.assertEqual(self.client.get('/api/jobs').json(), {'jobs': []})
        self.assertEqual(self.client.get('/api/jobs?limit=20').json(), {'jobs': [], 'next_cursor': None})

    def test_busy_cad_request_is_rejected_before_reservation(self):
        self.assertTrue(CAD_LOCK.acquire(blocking=False))
        try:
            with patch('print_agent.app.generate_model') as generate:
                response = self.client.post('/api/models', json={'template': 'tray'}, headers=self.headers)
                self.assertEqual(response.status_code, 409)
                self.assertEqual(response.json()['code'], 'resource_busy')
                self.assertEqual(response.headers['retry-after'], '2')
                generate.assert_not_called()
                self.assertEqual(self.app.state.store.list_jobs(), [])
        finally:
            CAD_LOCK.release()

    def test_failed_generation_retains_its_typed_request(self):
        with patch('print_agent.app.generate_model', side_effect=RuntimeError('private synthetic exception')):
            response = self.client.post('/api/models', json={'template': 'tray', 'width': 137}, headers=self.headers)
        self.assertEqual(response.status_code, 500)
        job = self.app.state.store.get(self.app.state.store.list_jobs()[0]['id'])
        self.assertEqual(job['request'], GeometryRequest(template='tray', width=137).model_dump())
        self.assertEqual(job['status'], 'failed')
        self.assertFalse(job['artifacts'])
        self.assertNotIn('private synthetic exception', json.dumps(job))

    def test_changed_download_and_bundle_return_integrity_conflict(self):
        job, folder = self.saved_job()
        original = self.client.get(job['artifacts']['three_mf'])
        self.assertEqual(original.status_code, 200)
        self.assertEqual(original.content, b'synthetic receipt fixture')
        self.assertIn('attachment', original.headers['content-disposition'])
        damaged = b'damaged synthetic bytes'
        (folder / 'model.3mf').write_bytes(damaged)
        for path in (job['artifacts']['three_mf'], job['bundle_url']):
            response = self.client.get(path)
            self.assertEqual(response.status_code, 409)
            self.assertEqual(response.json()['code'], 'artifact_integrity')
            self.assertNotIn(damaged, response.content)
        self.assertEqual((folder / 'model.3mf').read_bytes(), damaged)

    def test_unreadable_record_is_explainable_and_preserved(self):
        job, folder = self.saved_job()
        damaged = b'{incomplete record'
        (folder / 'job.json').write_bytes(damaged)
        response = self.client.get('/api/jobs/' + job['id'])
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()['code'], 'job_record_unreadable')
        self.assertEqual((folder / 'job.json').read_bytes(), damaged)

    def test_history_pages_can_reach_records_past_the_legacy_hundred(self):
        expected = set()
        for _ in range(103):
            job_id, _folder = self.app.state.store.reserve()
            self.app.state.store.fail(job_id, 'synthetic completed attempt')
            expected.add(job_id)
        self.assertEqual(len(self.client.get('/api/jobs').json()['jobs']), 100)
        seen, cursor = [], None
        while True:
            params = {'limit': 17}
            if cursor:
                params['before'] = cursor
            response = self.client.get('/api/jobs', params=params)
            self.assertEqual(response.status_code, 200)
            payload = response.json()
            self.assertLessEqual(len(payload['jobs']), 17)
            seen.extend(job['id'] for job in payload['jobs'])
            cursor = payload['next_cursor']
            if not cursor:
                break
        self.assertEqual(set(seen), expected)
        self.assertEqual(len(seen), 103)
        for params in ({'limit': 0}, {'limit': 101}, {'before': '../outside'}):
            self.assertEqual(self.client.get('/api/jobs', params=params).status_code, 422)

    def test_busy_slicer_does_not_execute_or_replace_record(self):
        job, _folder = self.saved_job()
        self.assertTrue(SLICER_LOCK.acquire(blocking=False))
        try:
            with patch('print_agent.app.prepare_slice') as prepare, patch('print_agent.app.probe_environment') as probe:
                for path, body in (('/api/slicer/probe', {}),
                                   ('/api/slice', {'job_id': job['id'], 'config_bundle': {}, 'execute': False})):
                    response = self.client.post(path, json=body, headers=self.headers)
                    self.assertEqual(response.status_code, 409)
                    self.assertEqual(response.json()['code'], 'resource_busy')
                prepare.assert_not_called()
                probe.assert_not_called()
                self.assertIsNone(self.app.state.store.get(job['id'])['latest_slice'])
        finally:
            SLICER_LOCK.release()

    def test_storage_failure_does_not_echo_private_os_details(self):
        job, _folder = self.saved_job()
        with patch.object(self.app.state.store, 'record_outcome', side_effect=OSError('synthetic private path and token')):
            response = self.client.post('/api/jobs/' + job['id'] + '/outcome',
                                        json={'result': 'not_tested'}, headers=self.headers)
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()['code'], 'storage_unavailable')
        self.assertNotIn('synthetic private', response.text)

    def test_failed_new_slice_never_restores_a_previous_slice_download(self):
        job, folder = self.saved_job()
        previous = folder / 'previous.gcode.3mf'
        previous.write_bytes(b'synthetic old sliced bytes')
        self.app.state.store.record_slice(job['id'], {'ready': True},
            {'status': 'sliced', 'output_path': str(previous)})
        with patch('print_agent.app.prepare_slice', side_effect=ValueError('잘못된 합성 설정')):
            response = self.client.post('/api/slice',
                json={'job_id': job['id'], 'config_bundle': {}, 'execute': False}, headers=self.headers)
        self.assertEqual(response.status_code, 422)
        saved = self.app.state.store.get(job['id'])
        self.assertNotIn('sliced_three_mf', saved['artifacts'])
        self.assertEqual(saved['latest_slice']['execution']['status'], 'failed')
        self.assertEqual(previous.read_bytes(), b'synthetic old sliced bytes')

    def test_changed_source_invalidates_previous_slice_when_new_attempt_is_admitted(self):
        job, folder = self.saved_job()
        previous = folder / 'previous.gcode.3mf'
        previous.write_bytes(b'synthetic prior result')
        self.app.state.store.record_slice(job['id'], {'ready': True},
            {'status': 'sliced', 'output_path': str(previous)})
        (folder / 'model.3mf').write_bytes(b'synthetic damaged model')
        with patch('print_agent.app.prepare_slice') as prepare:
            response = self.client.post('/api/slice',
                json={'job_id': job['id'], 'config_bundle': {}, 'execute': False}, headers=self.headers)
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()['code'], 'artifact_integrity')
        prepare.assert_not_called()
        saved = self.app.state.store.get(job['id'])
        self.assertNotIn('sliced_three_mf', saved['artifacts'])
        self.assertEqual(saved['latest_slice']['execution']['status'], 'failed')
        self.assertEqual(self.client.get('/api/jobs/' + job['id'] + '/files/sliced_three_mf').status_code, 404)


class ProductionLifespanTests(unittest.TestCase):
    def test_startup_recovers_only_while_holding_lease_and_releases_after_shutdown(self):
        from print_agent.runtime import DataDirectoryInUse
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / '작업 공간'
            store = JobStore(root)
            job_id, _folder = store.reserve(request={'template': 'tray', 'width': 133})
            with TestClient(create_app(root), base_url='http://127.0.0.1') as client:
                self.assertEqual(client.get('/api/jobs/' + job_id).json()['status'], 'interrupted')
                self.assertEqual(client.get('/api/bootstrap').json()['storage']['recovery']['interrupted'], 1)
                with self.assertRaises(DataDirectoryInUse):
                    with TestClient(create_app(root), base_url='http://127.0.0.1'):
                        self.fail('A second app must not own the same root')
            with TestClient(create_app(root), base_url='http://127.0.0.1') as restarted:
                job = restarted.get('/api/jobs/' + job_id).json()
                self.assertEqual(job['status'], 'interrupted')
                self.assertEqual(job['request']['width'], 133)
                self.assertEqual(restarted.get('/api/bootstrap').json()['storage']['recovery']['interrupted'], 0)
