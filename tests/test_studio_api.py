"""Real source imports and prepared-project API lifecycle without native Studio."""
import base64
import hashlib
import io
import json
import os
from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import patch
import zipfile

from fastapi.testclient import TestClient
from print_agent.app import create_app
from tests.studio_project_fixtures import project_bytes

REPO = Path(__file__).resolve().parents[1]


class StudioProjectAPITests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.app = create_app(Path(self.temp.name), test_mode=True)
        self.client = TestClient(self.app)
        self.headers = {'X-Session-Token': self.client.get('/api/bootstrap').json()['session_token']}
        self.raw = project_bytes()
        self.payload = {'filename': '설정 원본.3mf', 'content_base64': base64.b64encode(self.raw).decode('ascii')}

    def tearDown(self):
        self.client.close()
        self.temp.cleanup()

    def import_source(self, payload=None):
        response = self.client.post('/api/studio-projects/import', json=payload or self.payload, headers=self.headers)
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()

    def make_job(self):
        store = self.app.state.store
        job_id, folder = store.reserve()
        (folder / 'model.3mf').write_bytes((REPO / 'examples/cable_comb/model.3mf').read_bytes())
        return store.finish(job_id, {'template': 'cable_comb', 'parameters': {'template': 'cable_comb'},
            'dimensions_mm': {'x': 80, 'y': 18, 'z': 12}, 'volume_mm3': 100,
            'geometry_status': 'validated', 'print_status': 'not_tested',
            'files': {'three_mf': 'model.3mf'}, 'checks': [], 'warnings': []})

    def test_import_requires_session_origin_json_and_bounded_shape(self):
        endpoint = '/api/studio-projects/import'
        self.assertEqual(self.client.post(endpoint, json=self.payload).status_code, 403)
        self.assertEqual(self.client.post(endpoint, json=self.payload,
            headers={**self.headers, 'Origin': 'https://other.example'}).status_code, 403)
        self.assertEqual(self.client.post(endpoint, content=b'not json', headers=self.headers).status_code, 415)
        for changed in ({'content_base64': '!'}, {'filename': '../settings.3mf'}, {'path': '/tmp/source.3mf'}):
            response = self.client.post(endpoint, json={**self.payload, **changed}, headers=self.headers)
            self.assertEqual(response.status_code, 422, response.text)
        self.assertEqual(list((Path(self.temp.name) / 'studio-projects').iterdir()), [])

    def test_import_and_verified_original_download_without_cad_or_studio(self):
        source = self.import_source()
        self.assertTrue(source['supported'], source)
        self.assertNotIn('settings_text', source)
        self.assertNotIn('expected_settings', source)
        self.assertEqual(source, self.client.get('/api/studio-projects/' + source['source_id']).json())
        response = self.client.get(source['archive_url'])
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.content, self.raw)
        self.assertEqual(response.headers['content-type'], 'model/3mf')
        self.assertIn("filename*=utf-8''", response.headers['content-disposition'])
        self.assertEqual(self.client.get('/api/jobs').json()['jobs'], [])

    def test_dedicated_import_budget_does_not_expand_other_endpoints(self):
        raw = project_bytes(extra_members={'Metadata/unused.bin': os.urandom(2 * 1024 * 1024)})
        source = self.import_source({'filename': 'large.3mf', 'content_base64': base64.b64encode(raw).decode()})
        self.assertEqual(source['source']['bytes'], len(raw))
        for endpoint, limit in (('/api/studio-projects/import', 24), ('/api/slice', 8), ('/api/plan', 2)):
            response = self.client.post(endpoint, content=b'{}', headers={**self.headers,
                'Content-Type': 'application/json', 'Content-Length': str(limit * 1024 * 1024 + 1)})
            self.assertEqual(response.status_code, 413)
            self.assertIn(f'{limit} MiB', response.json()['detail'])

    def test_unsupported_source_stays_inspectable_and_original_is_preserved(self):
        raw = project_bytes(settings_overrides={'nozzle_diameter': ['0.4', '0.6']})
        source = self.import_source({'filename': 'unsupported.3mf', 'content_base64': base64.b64encode(raw).decode()})
        self.assertFalse(source['supported'])
        self.assertTrue(source['issues'])
        self.assertEqual(self.client.get(source['archive_url']).content, raw)

    def test_unsupported_zip_extract_version_is_actionable_and_atomic(self):
        malformed = bytearray(self.raw)
        struct.pack_into('<H', malformed, malformed.find(b'PK\x01\x02') + 6, 99)
        # Do not let TestClient rethrow the server exception: this regression
        # checks the user-visible HTTP boundary as well as atomic publication.
        with TestClient(self.app, raise_server_exceptions=False) as client:
            response = client.post('/api/studio-projects/import', headers=self.headers,
                json={'filename': 'unsupported-zip.3mf', 'content_base64': base64.b64encode(malformed).decode()})
        self.assertEqual(response.status_code, 422, response.text)
        self.assertTrue(response.json()['detail'])
        self.assertEqual(list((Path(self.temp.name) / 'studio-projects').iterdir()), [])

    def test_slice_requires_exactly_one_source_and_rejects_client_commands(self):
        for payload in ({'job_id': 'a' * 32},
                        {'job_id': 'a' * 32, 'config_bundle': {}, 'studio_project_id': 'b' * 32},
                        {'job_id': 'a' * 32, 'studio_project_id': '../escape'},
                        {'job_id': 'a' * 32, 'studio_project_id': 'b' * 32, 'executable_path': '/tmp/run'}):
            self.assertEqual(self.client.post('/api/slice', json=payload, headers=self.headers).status_code, 422)

    def test_source_tampering_is_conflict_for_inspection_and_download(self):
        source = self.import_source()
        folder = Path(self.temp.name) / 'studio-projects' / source['source_id']
        (folder / 'source.3mf').write_bytes(b'changed')
        for path in ('/api/studio-projects/' + source['source_id'], source['archive_url']):
            response = self.client.get(path)
            self.assertEqual(response.status_code, 409, response.text)
            self.assertEqual(response.json()['code'], 'studio_source_integrity')

    def test_missing_source_is_not_a_server_failure_and_detaches_previous_preparation(self):
        source = self.import_source()
        job = self.make_job()
        with patch('print_agent.slicer.detect_environment', return_value={'available': False, 'path': None,
                'diagnostics': ['No native installation in this API test'], 'printer_status': 'not_checked'}):
            response = self.client.post('/api/slice', json={'job_id': job['id'],
                'studio_project_id': source['source_id']}, headers=self.headers)
        self.assertEqual(response.status_code, 200, response.text)
        self.assertIn('prepared_three_mf', self.client.get('/api/jobs/' + job['id']).json()['artifacts'])
        response = self.client.post('/api/slice', json={'job_id': job['id'],
            'studio_project_id': 'a' * 32}, headers=self.headers)
        self.assertEqual(response.status_code, 404, response.text)
        saved = self.client.get('/api/jobs/' + job['id']).json()
        self.assertNotIn('prepared_three_mf', saved['artifacts'])
        self.assertEqual(saved['latest_slice']['execution']['status'], 'failed')

    def test_prepare_download_history_and_changed_source_detach_prior_result(self):
        source = self.import_source()
        job = self.make_job()
        request = {'job_id': job['id'], 'studio_project_id': source['source_id'], 'execute': False}
        with patch('print_agent.slicer.detect_environment', return_value={'available': False, 'path': None,
                'diagnostics': ['No native installation in this API test'], 'printer_status': 'not_checked'}):
            response = self.client.post('/api/slice', json=request, headers=self.headers)
        self.assertEqual(response.status_code, 200, response.text)
        data = response.json()
        self.assertTrue(data['plan']['project_prepared'])
        self.assertFalse(data['plan']['ready'])
        self.assertIsNone(data['execution'])
        self.assertEqual(data['plan']['project_source']['source_id'], source['source_id'])
        saved = self.client.get('/api/jobs/' + job['id']).json()
        self.assertIn('prepared_three_mf', saved['artifacts'])
        self.assertNotIn('sliced_three_mf', saved['artifacts'])
        prepared = self.client.get(saved['artifacts']['prepared_three_mf'])
        self.assertEqual(prepared.status_code, 200, prepared.text[:100])
        self.assertEqual(hashlib.sha256(prepared.content).hexdigest(), data['plan']['project_sha256'])
        with zipfile.ZipFile(io.BytesIO(prepared.content)) as archive, zipfile.ZipFile(io.BytesIO(self.raw)) as source_zip:
            self.assertEqual(archive.read('Metadata/project_settings.config'), source_zip.read('Metadata/project_settings.config'))
        self.assertEqual(self.client.get(source['archive_url']).content, self.raw)
        (Path(self.temp.name) / 'studio-projects' / source['source_id'] / 'source.3mf').write_bytes(b'changed')
        response = self.client.post('/api/slice', json=request, headers=self.headers)
        self.assertEqual(response.status_code, 409, response.text)
        saved = self.client.get('/api/jobs/' + job['id']).json()
        self.assertNotIn('prepared_three_mf', saved['artifacts'])
        self.assertEqual(saved['latest_slice']['execution']['status'], 'failed')
        self.assertEqual(self.client.get('/api/jobs/' + job['id'] + '/files/prepared_three_mf').status_code, 404)
