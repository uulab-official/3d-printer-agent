"""Real HTTP revision workflow: immutable originals, effective CAD and recovery."""
import base64
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile

from fastapi.testclient import TestClient

from print_agent.app import create_app
from print_agent.backup import create_backup, restore_backup
from tests.studio_project_fixtures import project_bytes


REPO = Path(__file__).resolve().parents[1]
VALUES = {'nozzle_temperature': '225', 'nozzle_temperature_initial_layer': '230',
          'filament_flow_ratio': '0.98', 'filament_max_volumetric_speed': '7.5',
          'bed_temperature': '60', 'bed_temperature_initial_layer': '65'}
NATIVE_VALUES = {'nozzle_temperature': ['225'], 'nozzle_temperature_initial_layer': ['230'],
                 'filament_flow_ratio': ['0.98'], 'filament_max_volumetric_speed': ['7.5'],
                 'hot_plate_temp': ['60'], 'hot_plate_temp_initial_layer': ['65']}
NO_NATIVE = {'available': False, 'path': None,
             'diagnostics': ['No native installation in this API fixture'], 'printer_status': 'not_checked'}


class StudioSettingsAPITests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name) / 'original workspace'
        self.app = create_app(self.root, test_mode=True)
        self.client = TestClient(self.app)
        self.headers = {'X-Session-Token': self.client.get('/api/bootstrap').json()['session_token']}
        self.raw = project_bytes()
        response = self.client.post('/api/studio-projects/import', headers=self.headers,
                                    json={'filename': '원본 설정.3mf',
                                          'content_base64': base64.b64encode(self.raw).decode('ascii')})
        self.assertEqual(response.status_code, 201, response.text)
        self.source = response.json()
        self.prefix = '/api/studio-projects/' + self.source['source_id'] + '/settings'
        self.proposal = {'source_sha256': self.source['source']['sha256'],
                         'settings_sha256': self.source['settings_sha256'], 'values': dict(VALUES)}

    def tearDown(self):
        self.client.close()
        self.temp.cleanup()

    def make_revision(self, proposal=None):
        proposal = self.proposal if proposal is None else proposal
        response = self.client.post(self.prefix + '/review', json=proposal, headers=self.headers)
        self.assertEqual(response.status_code, 200, response.text)
        review = response.json()
        response = self.client.post(self.prefix + '/revisions', headers=self.headers,
                                    json={**proposal, 'review_sha256': review['review_sha256']})
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

    def prepare(self, job_id, revision_id, client=None, headers=None):
        with patch('print_agent.slicer.detect_environment', return_value=NO_NATIVE):
            return (client or self.client).post('/api/slice', headers=headers or self.headers,
                json={'job_id': job_id, 'studio_settings_revision_id': revision_id, 'execute': False})

    def test_editor_exposes_only_six_bound_fields_before_cad_exists(self):
        response = self.client.get(self.prefix)
        self.assertEqual(response.status_code, 200, response.text)
        editor = response.json()
        self.assertEqual(editor['source_id'], self.source['source_id'])
        fields = {field['key']: field for field in editor['fields']}
        self.assertEqual(set(fields), set(VALUES))
        self.assertEqual(fields['bed_temperature']['native_key'], 'hot_plate_temp')
        self.assertEqual(fields['bed_temperature']['original'], '50')
        self.assertEqual(fields['bed_temperature_initial_layer']['original'], '55')
        self.assertEqual(fields['nozzle_temperature']['maximum'], 360)
        self.assertEqual(fields['bed_temperature']['maximum'], 120)
        self.assertNotIn('settings_text', editor)
        self.assertEqual(self.client.get('/api/jobs').json()['jobs'], [])

    def test_v07_source_receipt_and_revision_remain_readable_and_preparable(self):
        saved = self.make_revision()
        source_id = self.source['source_id']
        receipt_path = self.root / 'studio-projects' / source_id / 'receipt.json'
        receipt = json.loads(receipt_path.read_bytes())
        # Version 0.7 persisted this canonical inspection without display-only
        # volume fields. Upgrading must not reinterpret it as changed evidence.
        for key in ('printable_area', 'printable_height'):
            receipt['inspection']['summary'].pop(key, None)
        receipt_path.write_text(json.dumps(receipt), encoding='utf-8')
        original_receipt = receipt_path.read_bytes()
        revision_id = saved['revision']['revision_id']
        revision_path = self.root / 'studio-settings-revisions' / revision_id / 'revision.json'
        original_revision = revision_path.read_bytes()

        with TestClient(create_app(self.root, test_mode=True)) as reopened:
            source_response = reopened.get('/api/studio-projects/' + source_id)
            self.assertEqual(source_response.status_code, 200, source_response.text)
            source = source_response.json()
            self.assertEqual(source['summary']['printable_height'], '256')
            self.assertEqual(reopened.get(source['archive_url']).content, self.raw)
            revision_response = reopened.get('/api/studio-settings-revisions/' + revision_id)
            self.assertEqual(revision_response.status_code, 200, revision_response.text)
            self.assertEqual(revision_response.json()['revision'], saved['revision'])
            job = self.make_job()
            headers = {'X-Session-Token': reopened.get('/api/bootstrap').json()['session_token']}
            prepared = self.prepare(job['id'], revision_id, reopened, headers)
            self.assertEqual(prepared.status_code, 200, prepared.text)
            plan = prepared.json()['plan']
            self.assertTrue(plan['project_prepared'], plan['diagnostics'])
            self.assertTrue(plan['print_volume']['can_prepare'])
            self.assertEqual(plan['project_source']['summary'], source['summary'])

        self.assertEqual(receipt_path.read_bytes(), original_receipt)
        self.assertEqual(revision_path.read_bytes(), original_revision)

    def test_review_create_read_preserve_original_and_explicit_user_changes(self):
        response = self.client.post(self.prefix + '/review', json=self.proposal, headers=self.headers)
        self.assertEqual(response.status_code, 200, response.text)
        review = response.json()
        self.assertEqual(review['source_id'], self.source['source_id'])
        self.assertEqual(review['changed_count'], 6)
        self.assertEqual(review['provenance'], 'user_selected')
        self.assertEqual({change['native_key']: change['after'] for change in review['changes']}, NATIVE_VALUES)
        self.assertNotEqual(review['effective_settings_sha256'], self.source['settings_sha256'])
        self.assertEqual(list(self.root.rglob('revision.json')), [])
        saved = self.make_revision()
        record = saved['revision']
        self.assertRegex(record['revision_id'], '^[a-f0-9]{32}$')
        self.assertEqual(record['source_id'], self.source['source_id'])
        self.assertEqual(saved['source'], self.source)
        self.assertEqual(saved['review']['review_sha256'], review['review_sha256'])
        reread = self.client.get('/api/studio-settings-revisions/' + record['revision_id'])
        self.assertEqual(reread.status_code, 200, reread.text)
        self.assertEqual(reread.json(), saved)
        self.assertEqual(self.client.get(self.source['archive_url']).content, self.raw)
        self.assertEqual(self.client.get('/api/studio-projects/' + self.source['source_id']).json(), self.source)

    def test_review_and_creation_require_local_session_origin_and_json(self):
        for path in (self.prefix + '/review', self.prefix + '/revisions'):
            self.assertEqual(self.client.post(path, json=self.proposal).status_code, 403)
            self.assertEqual(self.client.post(path, json=self.proposal,
                headers={**self.headers, 'Origin': 'https://foreign.example'}).status_code, 403)
            self.assertEqual(self.client.post(path, content='not json', headers=self.headers).status_code, 415)
            self.assertEqual(self.client.post(path, content='{}', headers={**self.headers,
                'Content-Type': 'application/json', 'Content-Length': str(2 * 1024 * 1024 + 1)}).status_code, 413)

    def test_invalid_proposals_are_atomic_and_cannot_supply_paths_or_receipts(self):
        invalid_values = ({'nozzle_temperature': '225.5'}, {'nozzle_temperature': '1e2'},
            {'bed_temperature': '0'}, {'bed_temperature': '121'}, {'filament_flow_ratio': '1.'},
            {'filament_flow_ratio': True}, {'filament_flow_ratio': 0.98}, {'filament_flow_ratio': None},
            {'filament_max_volumetric_speed': 'NaN'}, {'nozzle_temperature': '361'},
            {'filament_flow_ratio': '2.01'}, {'filament_max_volumetric_speed': '201'},
            {'printer_model': 'other'}, {'cool_plate_temp': '60'}, {'machine_start_gcode': 'M104 S999'},
            {'filament_flow_ratio': '1' * 33}, {'nozzle_temperature': ['225']})
        for changes in invalid_values:
            with self.subTest(changes=changes):
                proposal = {**self.proposal, 'values': {**VALUES, **changes}}
                response = self.client.post(self.prefix + '/review', json=proposal, headers=self.headers)
                self.assertEqual(response.status_code, 422, response.text)
        for changes in ({'source_sha256': '0' * 64}, {'settings_sha256': '0' * 64},
                        {'values': []}, {'settings_text': '{}'}, {'source_path': '/tmp/source.3mf'},
                        {'before': {'filament_flow_ratio': ['1']}}):
            response = self.client.post(self.prefix + '/review', json={**self.proposal, **changes}, headers=self.headers)
            self.assertEqual(response.status_code, 422, response.text)
        self.assertEqual(list(self.root.rglob('revision.json')), [])
        self.assertEqual(self.client.get(self.source['archive_url']).content, self.raw)

    def test_changed_review_hash_and_noop_cannot_publish_revisions(self):
        review = self.client.post(self.prefix + '/review', json=self.proposal, headers=self.headers)
        self.assertEqual(review.status_code, 200, review.text)
        for extra in ({'review_sha256': '0' * 64},
                      {'review_sha256': review.json()['review_sha256'], 'values': {'nozzle_temperature': '226'}},
                      {'review_sha256': review.json()['review_sha256'], 'revision_id': 'a' * 32},
                      {'review_sha256': review.json()['review_sha256'], 'effective_settings_sha256': '0' * 64}):
            response = self.client.post(self.prefix + '/revisions', json={**self.proposal, **extra}, headers=self.headers)
            self.assertEqual(response.status_code, 422, response.text)
        noop = {**self.proposal, 'values': {'filament_flow_ratio': '1.000000', 'nozzle_temperature': '200'}}
        result = self.client.post(self.prefix + '/review', json=noop, headers=self.headers)
        self.assertEqual(result.status_code, 200, result.text)
        self.assertEqual(result.json()['changed_count'], 0)
        self.assertEqual(result.json()['effective_settings_sha256'], self.source['settings_sha256'])
        response = self.client.post(self.prefix + '/revisions', headers=self.headers,
            json={**noop, 'review_sha256': result.json()['review_sha256']})
        self.assertEqual(response.status_code, 422, response.text)
        self.assertEqual(list(self.root.rglob('revision.json')), [])

    def test_revision_prepares_current_cad_and_effective_settings_without_native(self):
        saved = self.make_revision()
        job = self.make_job()
        response = self.prepare(job['id'], saved['revision']['revision_id'])
        self.assertEqual(response.status_code, 200, response.text)
        plan = response.json()['plan']
        self.assertTrue(plan['project_prepared'], plan)
        self.assertFalse(plan['ready'])
        self.assertIsNone(response.json()['execution'])
        self.assertEqual(plan['settings_revision'], saved['revision'])
        self.assertEqual(plan['project_source'], self.source)
        self.assertEqual(plan['settings_review'], saved['review'])
        self.assertFalse(plan['project_receipt']['settings_preserved'])
        for key, value in NATIVE_VALUES.items():
            self.assertEqual(plan['expected_settings'][key], value)
        history = self.client.get('/api/jobs/' + job['id']).json()
        self.assertEqual(history['latest_slice']['plan'], plan)
        self.assertNotIn('sliced_three_mf', history['artifacts'])
        download = self.client.get(history['artifacts']['prepared_three_mf'])
        self.assertEqual(download.status_code, 200)
        self.assertEqual(hashlib.sha256(download.content).hexdigest(), plan['project_sha256'])
        with zipfile.ZipFile(io.BytesIO(self.raw)) as original, zipfile.ZipFile(io.BytesIO(download.content)) as edited:
            before = json.loads(original.read('Metadata/project_settings.config'))
            effective_bytes = edited.read('Metadata/project_settings.config')
            self.assertEqual(json.loads(effective_bytes), {**before, **NATIVE_VALUES})
            self.assertEqual(hashlib.sha256(effective_bytes).hexdigest(), saved['review']['effective_settings_sha256'])
            self.assertEqual(edited.testzip(), None)
        self.assertEqual(self.client.get(self.source['archive_url']).content, self.raw)

    def test_slice_allows_exactly_one_source_and_no_client_revision_record(self):
        choices = {'config_bundle': {}, 'studio_project_id': self.source['source_id'],
                   'studio_settings_revision_id': 'b' * 32}
        for selected in ({}, choices, {'config_bundle': {}, 'studio_settings_revision_id': 'b' * 32},
                         {'studio_project_id': self.source['source_id'], 'studio_settings_revision_id': 'b' * 32},
                         {'studio_settings_revision_id': '../escape'},
                         {'studio_settings_revision_id': 'b' * 32, 'settings_revision': {}},
                         {'studio_settings_revision_id': 'b' * 32, 'executable_path': '/tmp/anything'}):
            response = self.client.post('/api/slice', json={'job_id': 'a' * 32, **selected}, headers=self.headers)
            self.assertEqual(response.status_code, 422, response.text)

    def test_missing_or_corrupt_revision_clears_previous_current_download(self):
        for corruption, status in (('missing', 404), ('changed', 409), ('wrong_id', 409), ('symlink', 409)):
            with self.subTest(corruption=corruption):
                saved = self.make_revision()
                rid = saved['revision']['revision_id']
                job = self.make_job()
                prepared = self.prepare(job['id'], rid)
                self.assertEqual(prepared.status_code, 200, prepared.text)
                self.assertTrue(prepared.json()['plan']['project_prepared'])
                path = self.root / 'studio-settings-revisions' / rid / 'revision.json'
                if corruption == 'missing':
                    path.unlink()
                elif corruption == 'symlink':
                    target = path.with_name('original-record.json')
                    path.rename(target)
                    path.symlink_to(target)
                else:
                    record = json.loads(path.read_text())
                    if corruption == 'changed':
                        record['proposal']['values']['nozzle_temperature'] = '226'
                    else:
                        record['revision_id'] = 'f' * 32
                    path.write_text(json.dumps(record))
                reread = self.client.get('/api/studio-settings-revisions/' + rid)
                self.assertEqual(reread.status_code, status, reread.text)
                failed = self.prepare(job['id'], rid)
                self.assertEqual(failed.status_code, status, failed.text)
                history = self.client.get('/api/jobs/' + job['id']).json()
                self.assertNotIn('prepared_three_mf', history['artifacts'])
                self.assertNotIn('sliced_three_mf', history['artifacts'])
                self.assertEqual(history['latest_slice']['execution']['status'], 'failed')

    def test_missing_source_is_404_and_changed_source_is_409_for_saved_revision(self):
        saved = self.make_revision()
        endpoint = '/api/studio-settings-revisions/' + saved['revision']['revision_id']
        source_dir = self.root / 'studio-projects' / self.source['source_id']
        archive = source_dir / 'source.3mf'
        archive.write_bytes(b'changed source')
        response = self.client.get(endpoint)
        self.assertEqual(response.status_code, 409, response.text)
        archive.write_bytes(self.raw)
        (source_dir / 'receipt.json').unlink()
        response = self.client.get(endpoint)
        self.assertEqual(response.status_code, 404, response.text)

    def test_unsupported_source_stays_original_and_cannot_create_revision(self):
        raw = project_bytes(settings_overrides={'version': '99.00.00.00'}, application='BambuStudio-99.00.00.00')
        response = self.client.post('/api/studio-projects/import', headers=self.headers,
            json={'filename': 'future.3mf', 'content_base64': base64.b64encode(raw).decode()})
        self.assertEqual(response.status_code, 201, response.text)
        source = response.json()
        prefix = '/api/studio-projects/' + source['source_id'] + '/settings'
        self.assertEqual(self.client.get(prefix).status_code, 422)
        proposal = {'source_sha256': source['source']['sha256'], 'settings_sha256': source['settings_sha256'], 'values': VALUES}
        self.assertEqual(self.client.post(prefix + '/review', json=proposal, headers=self.headers).status_code, 422)
        self.assertEqual(self.client.get(source['archive_url']).content, raw)

    def test_revision_survives_restart_backup_restore_and_fresh_preparation(self):
        saved = self.make_revision()
        rid = saved['revision']['revision_id']
        job = self.make_job()
        prepared = self.prepare(job['id'], rid)
        self.assertEqual(prepared.status_code, 200, prepared.text)
        first_hash = prepared.json()['plan']['project_sha256']
        endpoint = '/api/studio-settings-revisions/' + rid
        self.client.close()
        with TestClient(create_app(self.root, test_mode=True)) as reopened:
            self.assertEqual(reopened.get(endpoint).json(), saved)
            self.assertEqual(reopened.get('/api/jobs/' + job['id']).json()['latest_slice']['plan']['settings_revision'], saved['revision'])
        archive = Path(self.temp.name) / 'workspace.zip'
        restored = Path(self.temp.name) / '복원된 작업'
        create_backup(self.root, archive)
        restore_backup(archive, restored)
        original_record = self.root / 'studio-settings-revisions' / rid / 'revision.json'
        self.assertEqual(original_record.read_bytes(), (restored / original_record.relative_to(self.root)).read_bytes())
        with TestClient(create_app(restored, test_mode=True)) as client:
            self.assertEqual(client.get(endpoint).json(), saved)
            token = {'X-Session-Token': client.get('/api/bootstrap').json()['session_token']}
            fresh = self.prepare(job['id'], rid, client, token)
            self.assertEqual(fresh.status_code, 200, fresh.text)
            plan = fresh.json()['plan']
            self.assertTrue(plan['project_prepared'], plan)
            self.assertEqual(plan['project_sha256'], first_hash)
            self.assertTrue(Path(plan['job_dir']).is_relative_to(restored))
            self.assertNotEqual(plan['job_dir'], prepared.json()['plan']['job_dir'])


if __name__ == '__main__':
    unittest.main()
