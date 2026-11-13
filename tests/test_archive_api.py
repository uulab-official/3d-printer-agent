"""Original source-shaped archives exercise HTTP and provenance round trips.

These are synthetic inputs, not captured GUI exports or printer qualification.
"""
import base64
from copy import deepcopy
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
import zipfile

from fastapi.testclient import TestClient

from print_agent.app import create_app
from print_agent.preset_library import resolve_profile_documents
from tests.test_workspace_api import workspace_snapshot


def archive_fixture(profile=None):
    profile = profile if profile is not None else {
        'name': 'Synthetic child', 'from': 'User', 'inherits': 'Missing base',
        'filament_settings_id': ['Synthetic child'], 'nozzle_temperature': ['215'],
    }
    raw = (json.dumps(profile, ensure_ascii=False, indent=2) + '\n').encode('utf-8')
    member = 'Synthetic vendor/Synthetic child.json'
    manifest = {
        'version': '', 'bundle_id': 'synthetic-offline-fixture',
        'bundle_type': 'filament config bundle', 'filament_name': 'Synthetic child',
        'filament_vendor': [{'vendor': 'Synthetic vendor', 'filament_path': [member]}],
    }
    output = io.BytesIO()
    with zipfile.ZipFile(output, 'w', compression=zipfile.ZIP_STORED) as archive:
        archive.writestr('bundle_structure.json', json.dumps(manifest))
        archive.writestr(member, raw)
    content = output.getvalue()
    origin = {
        'type': 'bambu_preset_archive', 'archive_name': 'synthetic.bbsflmt',
        'archive_sha256': hashlib.sha256(content).hexdigest(),
        'member_path': member, 'member_sha256': hashlib.sha256(raw).hexdigest(),
    }
    return content, profile, raw.decode('utf-8'), origin


class ArchiveAPITests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.client = TestClient(create_app(self.root, test_mode=True))
        self.headers = {'X-Session-Token': self.client.get('/api/bootstrap').json()['session_token']}

    def tearDown(self):
        self.client.close()
        self.temp.cleanup()

    def payload(self, content=None):
        if content is None:
            content = archive_fixture()[0]
        return {'filename': 'synthetic.bbsflmt',
                'content_base64': base64.b64encode(content).decode('ascii')}

    def test_import_returns_original_settings_and_byte_identity_without_saving(self):
        content, profile, raw, origin = archive_fixture()
        response = self.client.post('/api/profiles/import-archive', json=self.payload(content), headers=self.headers)
        self.assertEqual(response.status_code, 200, response.text)
        result = response.json()
        self.assertEqual(result['schema_version'], 1)
        self.assertEqual(result['documents'], [{
            'filename': origin['member_path'], 'profile': profile,
            'draft_text': raw, 'origin': origin,
        }])
        self.assertEqual(result['archive']['sha256'], origin['archive_sha256'])
        self.assertNotIn('source', result['documents'][0]['profile'])
        self.assertNotIn('type', result['documents'][0]['profile'])
        self.assertEqual(self.client.get('/api/profile-workspaces').json(), {'workspaces': []})
        self.assertEqual(self.client.get('/api/jobs').json(), {'jobs': []})

    def test_import_keeps_local_session_origin_and_json_boundaries(self):
        path, payload = '/api/profiles/import-archive', self.payload()
        for headers in ({}, {**self.headers, 'Origin': 'https://untrusted.example'}):
            response = self.client.post(path, json=payload, headers=headers)
            self.assertEqual(response.status_code, 403, response.text)
        response = self.client.post(path, content=b'archive', headers={**self.headers, 'Content-Type': 'application/zip'})
        self.assertEqual(response.status_code, 415, response.text)
        response = self.client.post(path, json=payload, headers={**self.headers, 'Origin': 'http://testserver'})
        self.assertEqual(response.status_code, 200, response.text)

    def test_invalid_base64_and_unknown_payload_fields_do_not_save_anything(self):
        valid = self.payload()
        for payload in (
            {**valid, 'content_base64': '%%%bad%%%'},
            {**valid, 'content_base64': valid['content_base64'] + '\n'},
            {**valid, 'content_base64': ''},
            {**valid, 'execute': True},
            {**valid, 'content_base64': base64.b64encode(b'not a zip').decode()},
        ):
            with self.subTest(payload_keys=list(payload)):
                response = self.client.post('/api/profiles/import-archive', json=payload, headers=self.headers)
                self.assertEqual(response.status_code, 422, response.text)
        self.assertEqual(self.client.get('/api/profile-workspaces').json(), {'workspaces': []})
        self.assertEqual(self.client.get('/api/jobs').json(), {'jobs': []})

    def test_archive_request_budget_includes_base64_overhead(self):
        profile = {'name': 'Synthetic child', 'filament_settings_id': ['Synthetic child'],
                   'description': 'x' * (1600 * 1024)}
        payload = self.payload(archive_fixture(profile)[0])
        self.assertGreater(len(json.dumps(payload)), 2 * 1024 * 1024)
        response = self.client.post('/api/profiles/import-archive', json=payload, headers=self.headers)
        self.assertEqual(response.status_code, 200, response.text[:300])
        response = self.client.post('/api/profiles/import-archive', content=b'x' * (8 * 1024 * 1024 + 1),
            headers={**self.headers, 'Content-Type': 'application/json'})
        self.assertEqual(response.status_code, 413)

    def test_origin_survives_save_restart_and_review_without_becoming_authority(self):
        content, profile, raw, origin = archive_fixture()
        imported = self.client.post('/api/profiles/import-archive', json=self.payload(content), headers=self.headers)
        self.assertEqual(imported.status_code, 200, imported.text)
        snapshot = workspace_snapshot()
        snapshot['documents'] = imported.json()['documents']
        snapshot['documents'][0]['draft_text'] = '{"unfinished": '
        record = self.client.post('/api/profile-workspaces', json={
            'title': 'Archive work', 'snapshot': snapshot,
        }, headers=self.headers)
        self.assertEqual(record.status_code, 201, record.text)
        with TestClient(create_app(self.root, test_mode=True)) as restarted:
            loaded = restarted.get('/api/profile-workspaces/' + record.json()['id']).json()
            self.assertEqual(loaded['snapshot'], snapshot)
        document = {'filename': origin['member_path'], 'profile': profile, 'origin': origin}
        reviewed = self.client.post('/api/profiles/resolve', json={
            'documents': [document], 'target_name': profile['name'],
            'baseline': {'documents': [document], 'target_name': profile['name']},
        }, headers=self.headers)
        self.assertEqual(reviewed.status_code, 200, reviewed.text)
        report = reviewed.json()
        self.assertEqual(report['status'], 'needs_input')
        self.assertEqual(report['issues'][0]['code'], 'PARENT_NOT_FOUND')
        self.assertEqual(report['documents'][0]['origin'], origin)
        self.assertEqual(report['imported_documents'][0]['origin'], origin)
        self.assertEqual(report['documents'][0]['profile'], profile)
        self.assertFalse(report['full_config'])
        self.assertFalse(report['native_verified'])

    def test_invalid_origin_is_rejected_without_replacing_saved_workspace(self):
        snapshot = workspace_snapshot()
        snapshot['documents'][0]['origin'] = archive_fixture()[3]
        created = self.client.post('/api/profile-workspaces', json={
            'title': 'Origin work', 'snapshot': snapshot,
        }, headers=self.headers)
        self.assertEqual(created.status_code, 201, created.text)
        path = '/api/profile-workspaces/' + created.json()['id']
        mutations = [
            {'type': 'manufacturer_verified'}, {'archive_sha256': 'not-a-hash'},
            {'member_path': ''}, {'member_path': 'x' * 241},
            {'member_sha256': 123}, {'trusted': True},
        ]
        for mutation in mutations:
            invalid = deepcopy(snapshot)
            invalid['documents'][0]['origin'].update(mutation)
            response = self.client.put(path, json={
                'title': 'Rejected', 'snapshot': invalid, 'expected_revision': 1,
            }, headers=self.headers)
            self.assertEqual(response.status_code, 422, response.text)
            self.assertEqual(self.client.get(path).json(), created.json())
            document = {key: value for key, value in invalid['documents'][0].items() if key != 'draft_text'}
            response = self.client.post('/api/profiles/resolve', json={
                'documents': [document], 'target_name': document['profile']['settings']['name'],
            }, headers=self.headers)
            self.assertEqual(response.status_code, 422, response.text)


class OriginResolutionTests(unittest.TestCase):
    def test_origin_is_preserved_independently_without_changing_settings_or_hash(self):
        _, profile, _, origin = archive_fixture({'name': 'Synthetic child', 'filament_type': ['PLA']})
        plain = {'filename': origin['member_path'], 'profile': profile}
        sourced = {**plain, 'origin': origin}
        before = deepcopy(sourced)
        report = resolve_profile_documents([sourced], profile['name'], {}, baseline={
            'documents': [sourced], 'target_name': profile['name'],
        })
        original = resolve_profile_documents([plain], profile['name'], {})
        self.assertEqual(report['documents'][0]['sha256'], original['documents'][0]['sha256'])
        self.assertEqual(report['resolved_profile'], original['resolved_profile'])
        self.assertEqual(report['review']['source_authority'], 'unknown')
        self.assertEqual(report['review']['validation_status'], 'unverified')
        self.assertEqual(report['documents'][0]['origin'], origin)
        self.assertEqual(report['imported_documents'][0]['origin'], origin)
        self.assertEqual(report['edit_review']['status'], 'unchanged')
        report['documents'][0]['origin']['archive_name'] = 'changed.zip'
        self.assertEqual(sourced, before)
        self.assertEqual(report['imported_documents'][0]['origin'], origin)


if __name__ == '__main__':
    unittest.main()
