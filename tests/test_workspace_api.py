"""The local HTTP boundary for saved filament inputs, never cached verdicts."""
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest

from fastapi.testclient import TestClient

from print_agent.app import create_app
from tests.test_profiles import fixture_profile, fixture_setup


def workspace_snapshot():
    profile = fixture_profile()
    return {
        'schema_version': 1,
        'documents': [{'filename': 'synthetic.json', 'profile': profile,
                       'draft_text': '{"unfinished": '}],
        'target_index': 0,
        'profile_text': '',
        'setup': {key: str(value) for key, value in fixture_setup().items()},
    }


class WorkspaceAPITests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.app = create_app(self.root, test_mode=True)
        self.client = TestClient(self.app)
        self.headers = {'X-Session-Token': self.client.get('/api/bootstrap').json()['session_token']}

    def tearDown(self):
        self.client.close()
        self.temp.cleanup()

    def create(self, snapshot=None):
        response = self.client.post('/api/profile-workspaces', json={
            'title': '  Synthetic filament work  ',
            'snapshot': snapshot if snapshot is not None else workspace_snapshot(),
        }, headers=self.headers)
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()

    def test_create_reopen_update_conflict_and_delete(self):
        original = workspace_snapshot()
        record = self.create(original)
        self.assertEqual(record['title'], 'Synthetic filament work')
        self.assertEqual(record['revision'], 1)
        self.assertEqual(record['snapshot'], original)
        path = '/api/profile-workspaces/' + record['id']
        self.assertEqual(self.client.get(path).json(), record)
        listed = self.client.get('/api/profile-workspaces').json()['workspaces']
        self.assertEqual(listed[0]['id'], record['id'])
        self.assertEqual(listed[0]['document_count'], 1)
        self.assertNotIn('snapshot', listed[0])
        self.assertEqual(self.client.get('/api/jobs').json()['jobs'], [])

        changed = deepcopy(original)
        changed['documents'][0]['draft_text'] = '{"still unfinished":  '
        updated = self.client.put(path, json={
            'title': 'Edited work', 'snapshot': changed, 'expected_revision': 1,
        }, headers=self.headers)
        self.assertEqual(updated.status_code, 200, updated.text)
        self.assertEqual(updated.json()['revision'], 2)
        self.assertEqual(updated.json()['snapshot'], changed)

        for method, payload in (
            ('PUT', {'title': 'Old tab', 'snapshot': original, 'expected_revision': 1}),
            ('DELETE', {'expected_revision': 1}),
        ):
            response = self.client.request(method, path, json=payload, headers=self.headers)
            self.assertEqual(response.status_code, 409, response.text)
        self.assertEqual(self.client.get(path).json(), updated.json())
        deleted = self.client.request('DELETE', path, json={'expected_revision': 2}, headers=self.headers)
        self.assertEqual(deleted.status_code, 200, deleted.text)
        self.assertEqual(deleted.json(), {'deleted': True, 'id': record['id']})
        self.assertEqual(self.client.get(path).status_code, 404)
        self.assertEqual(self.client.get('/api/profile-workspaces').json(), {'workspaces': []})

    def test_saved_inputs_survive_an_app_restart_without_review(self):
        record = self.create()
        with TestClient(create_app(self.root, test_mode=True)) as restarted:
            loaded = restarted.get('/api/profile-workspaces/' + record['id'])
            self.assertEqual(loaded.status_code, 200, loaded.text)
            self.assertEqual(loaded.json(), record)
            self.assertNotIn('review', loaded.json()['snapshot'])
            self.assertEqual(loaded.json()['snapshot']['documents'][0]['draft_text'], '{"unfinished": ')

    def test_each_write_requires_session_and_same_origin(self):
        record = self.create()
        cases = [
            ('POST', '/api/profile-workspaces', {'title': 'New', 'snapshot': workspace_snapshot()}),
            ('PUT', '/api/profile-workspaces/' + record['id'], {
                'title': 'New', 'snapshot': workspace_snapshot(), 'expected_revision': 1}),
            ('DELETE', '/api/profile-workspaces/' + record['id'], {'expected_revision': 1}),
        ]
        for method, path, payload in cases:
            for headers in ({}, {**self.headers, 'Origin': 'https://untrusted.example'}):
                with self.subTest(method=method, headers=bool(headers)):
                    response = self.client.request(method, path, json=payload, headers=headers)
                    self.assertEqual(response.status_code, 403, response.text)
        self.assertEqual(self.client.get('/api/profile-workspaces/' + record['id']).json(), record)

    def test_strict_payload_and_revision_do_not_change_saved_work(self):
        record = self.create()
        path = '/api/profile-workspaces/' + record['id']
        for revision in (True, 0, -1, 1.5, '1'):
            response = self.client.put(path, json={
                'title': 'Rejected', 'snapshot': workspace_snapshot(), 'expected_revision': revision,
            }, headers=self.headers)
            self.assertEqual(response.status_code, 422, response.text)
        invalid = workspace_snapshot()
        invalid['review'] = {'decision': 'ready_to_prepare'}
        for payload in (
            {'title': ' ', 'snapshot': workspace_snapshot()},
            {'title': 'Invalid', 'snapshot': invalid},
            {'title': 'Invalid', 'snapshot': workspace_snapshot(), 'execute': True},
        ):
            response = self.client.post('/api/profile-workspaces', json=payload, headers=self.headers)
            self.assertEqual(response.status_code, 422, response.text)
        self.assertEqual(self.client.get(path).json(), record)

    def test_workspace_budget_accepts_original_and_large_unfinished_draft(self):
        snapshot = workspace_snapshot()
        snapshot['documents'][0]['draft_text'] = ' ' * (2 * 1024 * 1024 + 1) + '{'
        record = self.create(snapshot)
        self.assertEqual(record['snapshot'], snapshot)
        response = self.client.post('/api/profile-workspaces', content=b'x' * (8 * 1024 * 1024 + 1),
            headers={**self.headers, 'Content-Type': 'application/json'})
        self.assertEqual(response.status_code, 413)
        response = self.client.post('/api/plan', content=b'x' * (2 * 1024 * 1024 + 1),
            headers={**self.headers, 'Content-Type': 'application/json'})
        self.assertEqual(response.status_code, 413)

    def test_invalid_ids_are_not_filesystem_paths(self):
        for identifier in ('not-an-id', 'a' * 31, 'g' * 32):
            self.assertEqual(self.client.get('/api/profile-workspaces/' + identifier).status_code, 422)
        self.assertEqual(self.client.get('/api/profile-workspaces/' + 'a' * 32).status_code, 404)

    def test_resolve_compares_preserved_original_settings(self):
        setup = fixture_setup()
        original = fixture_profile()
        original['validation'] = {'status': 'measured_on_matching_setup', 'setup_fingerprint': setup}
        changed = deepcopy(original)
        changed['settings']['nozzle_temperature'] = ['235']
        target = changed['settings']['name']
        response = self.client.post('/api/profiles/resolve', json={
            'documents': [{'filename': 'synthetic.json', 'profile': changed}],
            'target_name': target, 'setup': setup,
            'baseline': {'documents': [{'filename': 'synthetic.json', 'profile': original}], 'target_name': target},
        }, headers=self.headers)
        self.assertEqual(response.status_code, 200, response.text)
        result = response.json()
        self.assertEqual(result['edit_review']['status'], 'changed')
        self.assertEqual(result['review']['validation_status'], 'stale')
        self.assertFalse(result['review']['can_prepare_profile'])
        self.assertEqual(result['imported_documents'][0]['profile'], original)
        self.assertEqual(result['documents'][0]['profile'], changed)

    def test_resolver_budget_accounts_for_originals_but_keeps_each_set_bounded(self):
        profile = {'name': 'Large synthetic preset', 'description': 'x' * (1100 * 1024)}
        documents = [{'filename': 'large.json', 'profile': profile}]
        payload = {'documents': documents, 'target_name': profile['name'],
                   'baseline': {'documents': documents, 'target_name': profile['name']}}
        self.assertGreater(len(json.dumps(payload)), 2 * 1024 * 1024)
        response = self.client.post('/api/profiles/resolve', json=payload, headers=self.headers)
        self.assertEqual(response.status_code, 200, response.text[:200])
        self.assertEqual(response.json()['edit_review']['status'], 'unchanged')
        oversized = {'documents': [{'filename': 'huge.json', 'profile': {
            'name': 'Too large', 'description': 'x' * (2 * 1024 * 1024),
        }}], 'target_name': 'Too large'}
        response = self.client.post('/api/profiles/resolve', json=oversized, headers=self.headers)
        self.assertEqual(response.status_code, 422, response.text[:200])


if __name__ == '__main__':
    unittest.main()
