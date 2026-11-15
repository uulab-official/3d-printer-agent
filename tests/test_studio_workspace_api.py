"""Public API recovery without CAD and verified model handoff regressions."""
import base64
from copy import deepcopy
import hashlib
import io
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch
import zipfile

from fastapi.testclient import TestClient

from print_agent.app import create_app
from tests.studio_project_fixtures import project_bytes
from tests.test_workspaces import workspace_snapshot


REPO = Path(__file__).resolve().parents[1]
NO_NATIVE = {'available': False, 'path': None, 'diagnostics': ['Synthetic no-native environment'],
             'printer_status': 'not_checked'}


class StudioWorkspaceAPITests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name) / 'data'
        self.app = create_app(self.root, test_mode=True)
        self.client = TestClient(self.app)
        self.headers = {'X-Session-Token': self.client.get('/api/bootstrap').json()['session_token']}
        self.source_bytes = project_bytes()
        self.source = self.import_source()

    def tearDown(self):
        self.client.close()
        self.temp.cleanup()

    def import_source(self):
        response = self.client.post('/api/studio-projects/import', headers=self.headers,
            json={'filename': '같은 이름.3mf', 'content_base64': base64.b64encode(self.source_bytes).decode('ascii')})
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()

    def snapshot(self, revision=None, draft=False):
        editor = self.client.get('/api/studio-projects/' + self.source['source_id'] + '/settings').json()
        values = {field['key']: field['value'] for field in editor['fields']}
        if draft:
            values.update(filament_flow_ratio=' 1. ', filament_max_volumetric_speed='x' * 33)
        return {'schema_version': 1, 'source_id': self.source['source_id'],
                'settings_revision_id': revision['revision']['revision_id'] if revision else None,
                'source_sha256': self.source['source']['sha256'],
                'settings_sha256': self.source['settings_sha256'],
                'effective_settings_sha256': revision['revision']['effective_settings_sha256'] if revision else self.source['settings_sha256'],
                'draft_values': values if draft else None}

    def revision(self):
        prefix = '/api/studio-projects/' + self.source['source_id'] + '/settings'
        proposal = {'source_sha256': self.source['source']['sha256'],
                    'settings_sha256': self.source['settings_sha256'], 'values': {'nozzle_temperature': '225'}}
        review = self.client.post(prefix + '/review', headers=self.headers, json=proposal)
        self.assertEqual(review.status_code, 200, review.text)
        response = self.client.post(prefix + '/revisions', headers=self.headers,
            json={**proposal, 'review_sha256': review.json()['review_sha256']})
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()

    def save(self, snapshot=None, title='내 설정'):
        response = self.client.post('/api/studio-workspaces', headers=self.headers,
            json={'title': title, 'snapshot': self.snapshot() if snapshot is None else snapshot})
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()

    def test_zero_job_original_edited_and_unfinished_draft_reopen_after_restart(self):
        original = self.save(title='원본')
        revision = self.revision()
        snapshot = self.snapshot(revision, draft=True)
        edited = self.save(snapshot, '수정 초안')
        self.assertEqual(self.client.get('/api/jobs').json(), {'jobs': []})
        self.client.close()
        self.app = create_app(self.root, test_mode=True)
        self.client = TestClient(self.app)
        listed = self.client.get('/api/studio-library?kind=workspaces').json()
        self.assertEqual({item['id'] for item in listed['items']}, {original['id'], edited['id']})
        self.assertNotIn('draft_values', json.dumps(listed))
        opened = self.client.get('/api/studio-workspaces/' + edited['id'])
        self.assertEqual(opened.status_code, 200, opened.text)
        envelope = opened.json()
        self.assertEqual(set(envelope), {'workspace', 'source', 'settings_revision', 'editor'})
        self.assertEqual(envelope['workspace']['snapshot'], snapshot)
        self.assertEqual(envelope['settings_revision'], revision)
        self.assertEqual(envelope['source'], self.source)
        self.assertEqual(envelope['editor']['source_id'], self.source['source_id'])
        self.assertEqual(envelope['editor']['settings_sha256'], self.source['settings_sha256'])
        self.assertEqual({field['key']: field['original'] for field in envelope['editor']['fields']}['nozzle_temperature'], '200')
        self.assertNotIn('ready', envelope)
        self.assertEqual(self.client.get('/api/jobs').json(), {'jobs': []})

    def test_catalog_discovers_equal_filename_originals_and_old_revision_without_workspace(self):
        other = self.import_source()
        revision = self.revision()
        ids, cursor = [], None
        for _ in range(3):
            page = self.client.get('/api/studio-library', params={
                'kind': 'sources', 'limit': 1, **({'before': cursor} if cursor else {})})
            self.assertEqual(page.status_code, 200, page.text)
            body = page.json()
            ids.extend(item['id'] for item in body['items'])
            self.assertTrue(all(item['metadata_status'] == 'recorded' for item in body['items']))
            cursor = body['next_cursor']
            if cursor is None:
                break
        self.assertIsNone(cursor)
        self.assertEqual(set(ids), {self.source['source_id'], other['source_id']})
        self.assertEqual(len(ids), 2)
        revisions = self.client.get('/api/studio-library?kind=revisions').json()['items']
        self.assertEqual([item['id'] for item in revisions], [revision['revision']['revision_id']])
        self.assertEqual(self.client.get('/api/studio-library?kind=workspaces').json()['items'], [])

    def test_mutations_require_local_token_same_origin_and_strict_body(self):
        payload = {'title': 'Settings', 'snapshot': self.snapshot()}
        self.assertEqual(self.client.post('/api/studio-workspaces', json=payload).status_code, 403)
        self.assertEqual(self.client.post('/api/studio-workspaces', json=payload,
            headers={**self.headers, 'Origin': 'https://foreign.example'}).status_code, 403)
        self.assertEqual(self.client.post('/api/studio-workspaces', json={**payload, 'ready': True},
            headers=self.headers).status_code, 422)
        saved = self.save()
        endpoint = '/api/studio-workspaces/' + saved['id']
        self.assertEqual(self.client.put(endpoint, json={**payload, 'expected_revision': 1}).status_code, 403)
        self.assertEqual(self.client.request('DELETE', endpoint, json={'expected_revision': 1}).status_code, 403)
        for value in (True, '1', 0):
            self.assertEqual(self.client.put(endpoint, json={**payload, 'expected_revision': value},
                headers=self.headers).status_code, 422)

    def test_conflicting_update_and_delete_keep_newer_snapshot_and_allow_copy(self):
        first = self.save()
        endpoint = '/api/studio-workspaces/' + first['id']
        newer = self.snapshot(draft=True)
        response = self.client.put(endpoint, headers=self.headers,
            json={'title': '더 새 입력', 'snapshot': newer, 'expected_revision': 1})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()['revision'], 2)
        self.assertEqual(self.client.put(endpoint, headers=self.headers,
            json={'title': '이전 창', 'snapshot': first['snapshot'], 'expected_revision': 1}).status_code, 409)
        self.assertEqual(self.client.request('DELETE', endpoint, headers=self.headers,
            json={'expected_revision': 1}).status_code, 409)
        self.assertEqual(self.client.get(endpoint).json()['workspace']['snapshot'], newer)
        copied = self.save(first['snapshot'], '이전 창 복사본')
        self.assertNotEqual(copied['id'], first['id'])
        self.assertEqual(copied['revision'], 1)

    def test_delete_named_workspace_keeps_immutable_original_and_revision(self):
        revision = self.revision()
        saved = self.save(self.snapshot(revision))
        endpoint = '/api/studio-workspaces/' + saved['id']
        response = self.client.request('DELETE', endpoint, headers=self.headers, json={'expected_revision': 1})
        self.assertEqual(response.status_code, 204, response.text)
        self.assertEqual(self.client.get(endpoint).status_code, 404)
        self.assertEqual(self.client.get(self.source['archive_url']).content, self.source_bytes)
        self.assertEqual(self.client.get('/api/studio-settings-revisions/' + revision['revision']['revision_id']).json(), revision)

    def test_missing_edited_recipe_is_integrity_failure_without_original_fallback(self):
        revision = self.revision()
        saved = self.save(self.snapshot(revision, draft=True))
        (self.root / 'studio-settings-revisions' / revision['revision']['revision_id'] / 'revision.json').unlink()
        response = self.client.get('/api/studio-workspaces/' + saved['id'])
        self.assertEqual(response.status_code, 409, response.text)
        self.assertEqual(response.json()['code'], 'studio_workspace_integrity')
        self.assertNotIn('source', response.json())
        self.assertEqual(self.client.get(self.source['archive_url']).content, self.source_bytes)

    def test_corrupt_named_row_isolated_in_catalog_and_rejected_on_open(self):
        bad = self.save(title='손상될 항목')
        good = self.save(title='정상 항목')
        malformed = deepcopy(bad['snapshot'])
        malformed['draft_values'] = {'filament_flow_ratio': '1.'}
        with sqlite3.connect(self.root / 'studio-workspaces.sqlite3') as db:
            db.execute('UPDATE studio_workspaces SET snapshot_json=? WHERE id=?', (json.dumps(malformed), bad['id']))
        listing = self.client.get('/api/studio-library?kind=workspaces')
        self.assertEqual(listing.status_code, 200, listing.text)
        items = {item['id']: item for item in listing.json()['items']}
        self.assertEqual(items[bad['id']]['metadata_status'], 'unreadable')
        self.assertEqual(items[good['id']]['metadata_status'], 'recorded')
        response = self.client.get('/api/studio-workspaces/' + bad['id'])
        self.assertEqual(response.status_code, 409, response.text)
        self.assertEqual(response.json()['code'], 'studio_workspace_integrity')
        self.assertEqual(self.client.get('/api/studio-workspaces/' + good['id']).status_code, 200)

    def test_missing_original_is_saved_workspace_integrity_for_original_and_edited(self):
        original = self.save()
        edited = self.save(self.snapshot(self.revision()))
        receipt = self.root / 'studio-projects' / self.source['source_id'] / 'receipt.json'
        receipt.unlink()
        for record in (original, edited):
            response = self.client.get('/api/studio-workspaces/' + record['id'])
            self.assertEqual(response.status_code, 409, response.text)
            self.assertEqual(response.json()['code'], 'studio_workspace_integrity')
        self.assertEqual(self.client.get('/api/studio-workspaces/' + '0' * 32).status_code, 404)
        self.assertEqual(self.client.get('/api/studio-projects/' + self.source['source_id']).status_code, 404)

    def test_corrupt_profile_workspace_returns_actionable_integrity_code(self):
        saved = self.app.state.workspaces.create('Raw inputs', workspace_snapshot())
        snapshot = saved['snapshot']
        snapshot['target_index'] = 99
        with sqlite3.connect(self.root / 'profile-workspaces.sqlite3') as db:
            db.execute('UPDATE profile_workspaces SET snapshot_json=? WHERE id=?', (json.dumps(snapshot), saved['id']))
        response = self.client.get('/api/profile-workspaces/' + saved['id'])
        self.assertEqual(response.status_code, 409, response.text)
        self.assertEqual(response.json()['code'], 'workspace_integrity')

    def test_reference_hash_mismatch_cannot_be_saved_as_a_different_source(self):
        snapshot = self.snapshot()
        snapshot['source_sha256'] = '0' * 64
        response = self.client.post('/api/studio-workspaces', headers=self.headers,
            json={'title': 'Wrong source', 'snapshot': snapshot})
        self.assertEqual(response.status_code, 422, response.text)
        self.assertEqual(self.client.get('/api/studio-library?kind=workspaces').json()['items'], [])

    def test_catalog_rejects_invalid_kind_cursor_and_bounds(self):
        for params in ({'kind': 'jobs'}, {'kind': 'sources', 'limit': 0},
                       {'kind': 'sources', 'limit': 101}, {'kind': 'sources', 'before': '../outside'}):
            response = self.client.get('/api/studio-library', params=params)
            self.assertEqual(response.status_code, 422, response.text)

    def test_slice_uses_verified_cad_snapshot_if_path_changes_after_read(self):
        store = self.app.state.store
        job_id, folder = store.reserve()
        original = (REPO / 'examples/cable_comb/model.3mf').read_bytes()
        replacement = (REPO / 'examples/tray/model.3mf').read_bytes()
        model_path = folder / 'model.3mf'
        model_path.write_bytes(original)
        store.finish(job_id, {'template': 'cable_comb', 'parameters': {'template': 'cable_comb'},
            'dimensions_mm': {'x': 80, 'y': 18, 'z': 12}, 'volume_mm3': 100,
            'geometry_status': 'validated', 'print_status': 'not_tested',
            'files': {'three_mf': 'model.3mf'}, 'checks': [], 'warnings': []})
        read = store.read_artifact

        def replace_after_verification(*args, **kwargs):
            value = read(*args, **kwargs)
            model_path.write_bytes(replacement)
            return value

        with patch.object(store, 'read_artifact', side_effect=replace_after_verification), \
                patch('print_agent.slicer.detect_environment', return_value=NO_NATIVE):
            response = self.client.post('/api/slice', headers=self.headers,
                json={'job_id': job_id, 'studio_project_id': self.source['source_id'], 'execute': False})
        if response.status_code == 200:
            plan = response.json()['plan']
            if plan['project_prepared']:
                self.assertEqual(plan['project_receipt']['model_sha256'], hashlib.sha256(original).hexdigest())
                with zipfile.ZipFile(io.BytesIO(Path(plan['project_path']).read_bytes())) as archive, \
                        zipfile.ZipFile(io.BytesIO(replacement)) as other:
                    self.assertNotEqual(archive.read('3D/3dmodel.model'),
                                        other.read('3D/3dmodel.model'))
        else:
            self.assertEqual(response.status_code, 409, response.text)
        # A changed on-disk original never gets a newly published replacement CAD.
        recorded = store.get(job_id)
        if 'prepared_three_mf' in recorded['artifacts']:
            self.assertEqual(recorded['latest_slice']['plan']['project_receipt']['model_sha256'],
                             hashlib.sha256(original).hexdigest())


if __name__ == '__main__':
    unittest.main()
